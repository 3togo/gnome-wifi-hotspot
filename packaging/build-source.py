#!/usr/bin/python3
"""Build unsigned Debian source/binary artifacts in an isolated local directory."""
import argparse
from email.utils import parsedate_to_datetime
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def source_files():
    if (ROOT / '.git').exists():
        names = set(subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0'))
        # Include newly added source modules before their first commit; never
        # silently include unrelated notes, local configuration, or build output.
        for directory in ('daemon', 'settings', 'tests', 'packaging'):
            names.update(str(path.relative_to(ROOT)) for path in (ROOT / directory).rglob('*')
                         if path.is_file() and '__pycache__' not in path.parts
                         and path.suffix not in {'.pyc', '.log'})
        names.update({'docs/production-readiness.md', 'docs/dependency-review.md',
                      'integration/gnome-settings/relay-entrypoint.patch',
                      'data/wifi-relay-gnome.desktop', 'data/wifi-relay-tray.desktop'})
    else:
        names = {str(path.relative_to(ROOT)) for path in ROOT.rglob('*')
                 if path.is_file() and not set(path.relative_to(ROOT).parts) & {'.git', 'dist', '__pycache__', 'debian'}}
    return sorted(name for name in names if name and (ROOT / name).is_file())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('version', nargs='?')
    parser.add_argument('--binary', action='store_true', help='Also build binaries and run package build tests')
    args = parser.parse_args()
    version = args.version or subprocess.check_output([
        'dpkg-parsechangelog', '-l', str(ROOT / 'packaging/debian/changelog'), '-S', 'Version'], text=True).strip()
    subprocess.run(['dpkg', '--validate-version', version], check=True)
    if '-' not in version:
        parser.error('A quilt source version needs a Debian revision, such as 1.0.0-13')
    upstream = version.split(':')[-1].rsplit('-', 1)[0]
    output = ROOT / 'dist'
    output.mkdir(exist_ok=True)
    environment = dict(os.environ)
    environment.pop('LD_PRELOAD', None)
    date = subprocess.check_output([
        'dpkg-parsechangelog', '-l', str(ROOT / 'packaging/debian/changelog'), '-S', 'Date'], text=True).strip()
    epoch = int(environment.get('SOURCE_DATE_EPOCH') or parsedate_to_datetime(date).timestamp())
    environment['SOURCE_DATE_EPOCH'] = str(epoch)
    log_path = output / f'gnome-wifi-hotspot_{version.split(":")[-1]}-source-build.log'
    with tempfile.TemporaryDirectory(prefix='relay-source-', dir=output) as directory:
        work = Path(directory)
        source = work / f'gnome-wifi-hotspot-{upstream}'
        source.mkdir()
        for name in source_files():
            destination = source / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, destination)
        def archive_metadata(member):
            member.uid = member.gid = 0
            member.uname = member.gname = 'root'
            member.mtime = epoch
            return member
        original = work / f'gnome-wifi-hotspot_{upstream}.orig.tar.xz'
        with tarfile.open(original, 'w:xz') as archive:
            archive.add(source, arcname=source.name, filter=archive_metadata)
        debian = source / 'debian'
        shutil.copytree(ROOT / 'packaging/source-debian', debian)
        controls = []
        for template in ('control', 'control-gnome', 'control-tray'):
            control = (ROOT / 'packaging/debian' / template).read_text()
            control = '\n'.join(line for line in control.split('\n')
                                if not line.startswith(('Version: ', 'Maintainer: ')))
            control = control.replace('@VERSION@', '${binary:Version}')
            substvars = '${misc:Depends}, ' if template == 'control-gnome' else '${misc:Depends}, ${python3:Depends}, '
            control = control.replace('Depends: ', 'Depends: ' + substvars, 1)
            controls.append(control.strip())
        control = '\n\n'.join(controls) + '\n'
        header = ('Source: gnome-wifi-hotspot\nSection: net\nPriority: optional\n'
                  'Maintainer: Erhan Zeyrek <erhanzeyrek@users.noreply.github.com>\n'
                  'Build-Depends: debhelper-compat (= 13), dh-python, python3, python3-gi, '
                  'gir1.2-gtk-4.0, gir1.2-adw-1, gir1.2-gtk-3.0, gir1.2-ayatanaappindicator3-0.1, '
                  'nodejs, dbus, xvfb, xauth, pkgconf, libgtk-3-dev, libjansson-dev\n'
                  'Standards-Version: 4.7.2\nRules-Requires-Root: no\n'
                  'Homepage: https://github.com/3togo/gnome-wifi-hotspot\n\n')
        (debian / 'control').write_text(header + control)
        changelog = (ROOT / 'packaging/debian/changelog').read_text()
        first, rest = changelog.split('\n', 1)
        first = 'gnome-wifi-hotspot (' + version + ') stonking; urgency=medium'
        (debian / 'changelog').write_text(first + '\n' + rest)
        (debian / 'copyright').write_text((ROOT / 'packaging/debian/copyright').read_text())
        for script in ('preinst', 'postinst', 'prerm', 'postrm'):
            target = debian / f'gnome-wifi-hotspot.{script}'
            content = (ROOT / f'packaging/debian/{script}').read_text()
            content = ''.join(line for line in content.splitlines(True)
                              if not line.startswith('dpkg-maintscript-helper rm_conffile '))
            target.write_text(content + '\n#DEBHELPER#\n')
            target.chmod(0o755)
        (debian / 'gnome-wifi-hotspot.maintscript').write_text(
            'rm_conffile /etc/xdg/autostart/wifi-hotspot-autostart.desktop 1.0.0-16~ gnome-wifi-hotspot\n')
        with log_path.open('w') as log:
            subprocess.run(['dpkg-source', '-b', '.'], cwd=source, env=environment,
                           stdout=log, stderr=subprocess.STDOUT, check=True)
            if not args.binary:
                changes = work / f'gnome-wifi-hotspot_{version.split(":")[-1]}_source.changes'
                with changes.open('w') as manifest:
                    subprocess.run(['dpkg-genchanges', '-S', '-sa'], cwd=source, env=environment,
                                   stdout=manifest, stderr=log, check=True)
            if args.binary:
                subprocess.run(['dpkg-buildpackage', '-b', '-uc', '-us'], cwd=source, env=environment,
                               stdout=log, stderr=subprocess.STDOUT, check=True)
        for artifact in work.iterdir():
            if artifact.is_file():
                shutil.copy2(artifact, output / artifact.name)
                print(output / artifact.name)
    print('Build log:', log_path)


if __name__ == '__main__':
    main()
