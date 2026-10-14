#!/usr/bin/env python3
"""Run validation and save source provenance, per-check results, and logs from bounded checks."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import signal
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT).decode().strip()


def source_manifest(output):
    names = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT)
    files = []
    for name in sorted(set(names.decode().split('\0')) - {''}):
        path = ROOT / name
        if path.is_relative_to(output):
            continue
        if path.is_symlink():
            data = os.readlink(path).encode()
        elif path.is_file():
            data = path.read_bytes()
        else:
            files.append({'path': name, 'missing': True})
            continue
        files.append({'path': name, 'sha256': hashlib.sha256(data).hexdigest(),
                      'mode': oct(path.lstat().st_mode & 0o777)})
    digest = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    return {'commit': git('rev-parse', 'HEAD'), 'worktree_status': git('status', '--porcelain'),
            'sha256': digest, 'files': files}


def run_check(name, command, output, timeout, environment=None):
    started = time.monotonic()
    log_path = output / (name + '.log')
    result = {'name': name, 'command': command, 'log': log_path.name}
    process = None
    with log_path.open('w') as log:
        try:
            process = subprocess.Popen(command, cwd=ROOT, env=environment,
                                       stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            result['exit_code'] = process.wait(timeout=timeout)
            result['status'] = 'pass' if result['exit_code'] == 0 else 'fail'
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            result.update(status='fail', reason=f'Timed out after {timeout} seconds')
        except OSError as error:
            result.update(status='blocked', reason=str(error))
    result['duration_seconds'] = round(time.monotonic() - started, 3)
    # Preserve measured counts, rather than copying release documentation counts.
    match = re.search(r'Ran (\d+) tests? in', log_path.read_text(errors='replace'))
    if match:
        result['test_count'] = int(match[1])
    print(f"{name}: {result['status']}", flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='New report directory (default: dist/validation/<UTC timestamp>)')
    parser.add_argument('--full', action='store_true', help='Include sanitized applet, GNOME, and extracted-package checks')
    parser.add_argument('--with-lifecycle', action='store_true', help='Also run install/upgrade/remove/purge in a disposable Docker container')
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc)
    output = (args.output or ROOT / 'dist/validation' / stamp.strftime('%Y%m%dT%H%M%S.%fZ')).resolve()
    output.mkdir(parents=True, exist_ok=False)
    provenance = source_manifest(output)
    report = {'status': 'running', 'started_at_utc': stamp.isoformat(), 'source': provenance,
              'environment': {'os_release': Path('/etc/os-release').read_text() if Path('/etc/os-release').exists() else None,
                              'kernel': platform.release(), 'python': platform.python_version(),
                              'display': 'xvfb' if shutil.which('xvfb-run') else
                              ('session' if os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY') else 'unavailable')},
              'checks': []}
    report_path = output / 'report.json'

    def save():
        report_path.write_text(json.dumps(report, indent=2) + '\n')

    def check(name, command, timeout=180, environment=None):
        result = run_check(name, command, output, timeout, environment)
        report['checks'].append(result)
        save()
        return result['status'] == 'pass'

    def not_run(name, reason):
        report['checks'].append({'name': name, 'status': 'not_run', 'reason': reason})
        save()

    save()
    check('unit', ['make', 'test'])
    check('service-integration', ['make', 'test-integration'])
    check('gtk-smoke', ['make', 'test-smoke'])
    check('syntax', ['bash', '-eu', '-c', '''
for script in extension/*.js; do node --input-type=module --check < "$script"; done
bash -n daemon/create_ap packaging/build-deb.sh
sh -n tests/run_smoke.sh tests/run_package_lifecycle.sh tests/check_package_lifecycle.sh \
    packaging/debian/preinst packaging/debian/postinst packaging/debian/prerm packaging/debian/postrm
'''])
    check('appstream', ['appstreamcli', 'validate', '--no-net', 'data/io.github.erhanzeyrek.WifiHotspot.metainfo.xml'])
    if args.full:
        environment = dict(os.environ, SANITIZE='1')
        environment.pop('LD_PRELOAD', None)
        if shutil.which('xvfb-run'):
            applet = ['dbus-run-session', '--', 'xvfb-run', '-a', 'make', 'test-nm-menu']
        else:
            applet = ['dbus-run-session', '--', 'make', 'test-nm-menu']
        check('sanitized-applet', applet, environment=environment)
        check('gnome-shell', ['tools/check_gnome_shell.sh'], timeout=90)
        package_environment = dict(os.environ, WIFI_RELAY_BUILD_OUTPUT=str(output / 'packages'))
        if check('packages-build', ['packaging/build-deb.sh'], environment=package_environment):
            root = output / 'package-root'
            packages = sorted((output / 'packages').glob('*.deb'))
            report['packages'] = [{'name': package.name, 'sha256': hashlib.sha256(package.read_bytes()).hexdigest()}
                                  for package in packages]
            extracted = True
            for package in packages:
                extracted = check('extract-' + package.name, ['dpkg-deb', '--extract', str(package), str(root)]) and extracted
            if extracted:
                environment = dict(os.environ, WIFI_RELAY_TEST_SETTINGS_DIR=str(root / 'usr/share/wifi-hotspot/settings'),
                                   WIFI_RELAY_TEST_DAEMON_DIR=str(root / 'usr/libexec/wifi-hotspot-daemon'))
                check('packaged-service-integration', ['make', 'test-integration'], environment=environment)
                check('packaged-gtk-smoke', ['make', 'test-smoke'], environment=environment)
            else:
                not_run('packaged-service-integration', 'Package extraction failed')
                not_run('packaged-gtk-smoke', 'Package extraction failed')
        else:
            not_run('packaged-service-integration', 'Package build failed')
            not_run('packaged-gtk-smoke', 'Package build failed')
    else:
        for name in ['sanitized-applet', 'gnome-shell', 'packages-build', 'packaged-service-integration', 'packaged-gtk-smoke']:
            not_run(name, 'Enable with --full')
    if args.with_lifecycle:
        check('package-lifecycle', ['make', 'test-package-lifecycle'], timeout=1800)
    else:
        not_run('package-lifecycle', 'Enable with --with-lifecycle; requires Docker and network access')
    not_run('hardware-traffic', 'Requires a physical multi-adapter test bench; see docs/release-hardware-validation.md')
    report['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
    report['source_unchanged'] = source_manifest(output)['sha256'] == provenance['sha256']
    report['status'] = 'pass' if report['source_unchanged'] and all(
        item['status'] in {'pass', 'not_run'} for item in report['checks']) else 'fail'
    save()
    print(f"Report: {report_path}")
    print(f"Executed checks: {report['status']}; unperformed checks remain not_run.")
    return 0 if report['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
