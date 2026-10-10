#!/usr/bin/env python3
"""Run local build checks and optional Ubuntu package builds without installing them."""

import argparse
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
INTEGRATIONS = {
    'nm-core': ROOT / 'integration/nm-core/build-deb.sh',
    'nm-applet': ROOT / 'integration/nm-applet/build-deb.sh',
    'gnome-settings': ROOT / 'integration/gnome-settings/build-deb.sh',
}
REQUIRED_TOOLS = ('dpkg', 'dpkg-parsechangelog', 'dpkg-deb', 'make', 'node', 'bash')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--full', action='store_true',
                        help='Also build Debian source and binary packages (needs Stonking build dependencies)')
    parser.add_argument('--integration', action='append', choices=(*INTEGRATIONS, 'all'), default=[],
                        help='Build a pinned Ubuntu integration; repeat or use all')
    parser.add_argument('--all-packages', action='store_true',
                        help='Export companion packages from selected integration builds')
    parser.add_argument('--cc', action='append', default=[], metavar='COMPILER',
                        help='C compiler for the applet harness; repeat for a matrix (default: installed gcc/clang)')
    parser.add_argument('--version', help='Debian version for the app packages (default: changelog version)')
    parser.add_argument('--dry-run', action='store_true', help='Print commands without running them')
    args = parser.parse_args()

    if args.all_packages and not args.integration:
        parser.error('--all-packages requires --integration')

    missing = [tool for tool in REQUIRED_TOOLS if not shutil.which(tool)]
    if args.full:
        missing.extend(tool for tool in ('dpkg-source', 'dpkg-buildpackage') if not shutil.which(tool))
    if args.integration:
        missing.extend(tool for tool in ('apt-get', 'dpkg-buildpackage', 'patch') if not shutil.which(tool))
    if missing:
        parser.error('Missing required tools: ' + ', '.join(missing))

    version = args.version
    if version is None:
        version = subprocess.check_output([
            'dpkg-parsechangelog', '-l', str(ROOT / 'packaging/debian/changelog'),
            '-S', 'Version'], text=True).strip()
    subprocess.run(['dpkg', '--validate-version', version], check=True)
    if args.full and '-' not in version:
        parser.error('--full needs a Debian revision in --version')

    selected = list(INTEGRATIONS) if 'all' in args.integration else list(dict.fromkeys(args.integration))
    compilers = list(dict.fromkeys(args.cc or [cc for cc in ('gcc', 'clang') if shutil.which(cc)]))
    if not compilers:
        parser.error('No C compiler found; install gcc or clang, or pass --cc')
    for cc in compilers:
        if not shutil.which(cc):
            parser.error(f'C compiler not found: {cc}')

    results = []

    def run(label, command, *, env=None):
        print(f'\n==> {label}: {shlex.join([str(x) for x in command])}', flush=True)
        if args.dry_run:
            results.append((label, 'planned'))
            return
        status = subprocess.run(command, cwd=ROOT, env=env, check=False).returncode
        results.append((label, 'PASS' if status == 0 else f'FAIL ({status})'))

    # Syntax checks avoid producing bytecode or modifying the working tree.
    python_files = [str(path) for folder in ('daemon', 'settings', 'packaging', 'tools', 'tests')
                    for path in sorted((ROOT / folder).rglob('*.py'))]
    run('Python syntax', [sys.executable, '-c',
                          'import pathlib,sys; [(compile(pathlib.Path(p).read_bytes(), p, "exec")) '
                          'for p in sys.argv[1:]]', *python_files])
    for path in sorted((ROOT / 'extension').glob('*.js')):
        # Node accepts module syntax from stdin, not from a .js file in this tree.
        run(f'JavaScript syntax: {path.name}', [sys.executable, '-c',
            'import pathlib,subprocess,sys; raise SystemExit(subprocess.run('
            '["node","--input-type=module","--check"], '
            'input=pathlib.Path(sys.argv[1]).read_bytes()).returncode)', str(path)])
    for path in sorted(ROOT.rglob('*.sh')):
        if 'dist' not in path.parts:
            run(f'Shell syntax: {path.relative_to(ROOT)}', ['bash', '-n', str(path)])
    run('create_ap syntax', ['bash', '-n', 'daemon/create_ap'])
    for name in ('preinst', 'postinst', 'prerm', 'postrm', 'postinst-tray', 'prerm-tray'):
        run(f'Maintainer script syntax: {name}', ['sh', '-n', f'packaging/debian/{name}'])
    run('unit and tray tests', ['make', 'test'])

    have_c_deps = shutil.which('pkg-config') and subprocess.run(
        ['pkg-config', '--exists', 'gtk+-3.0', 'gio-2.0', 'jansson'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    display = bool(os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY'))
    if args.dry_run or (have_c_deps and (display or shutil.which('xvfb-run'))):
        for cc in compilers:
            for opt_level, sanitized in ((0, False), (2, False), (1, True)):
                command = ['bash', 'integration/nm-applet/test.sh']
                if not display:
                    command = ['xvfb-run', '-a', *command]
                run(f'C applet: {cc}, -O{opt_level}, '
                    f'{"ASan+UBSan" if sanitized else "warnings"}', command,
                    env=dict(os.environ, CC=cc, OPT_LEVEL=str(opt_level),
                             SANITIZE='1' if sanitized else '0'))
    else:
        reason = 'GTK3/Gio/Jansson development files' if not have_c_deps else 'a display or xvfb-run'
        status = 'FAIL' if args.cc else 'SKIP'
        print(f'\n{status} C applet matrix: requires {reason}', flush=True)
        results.append(('C applet matrix', status))

    output = ROOT / 'dist/build-matrix/direct'
    run('direct Debian packages', ['bash', 'packaging/build-deb.sh', version],
        env=dict(os.environ, WIFI_RELAY_BUILD_OUTPUT=str(output)))
    if args.full:
        run('Debian source and binary packages', [sys.executable, 'packaging/build-source.py',
                                                   version, '--binary'])
    for name in selected:
        command = ['bash', str(INTEGRATIONS[name])]
        if args.all_packages:
            # An empty first argument uses each builder's pinned default version.
            command += ['', '--all']
        run(f'{name} Ubuntu packages', command)

    print('\nBuild matrix summary:')
    for label, result in results:
        print(f'  {result:10} {label}')
    if any(result.startswith('FAIL') for _, result in results):
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
