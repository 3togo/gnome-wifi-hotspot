#!/usr/bin/python3
"""Create a monolithic ownership fixture for disposable-container upgrade tests.

This fixture represents the old layout, not an old software release. Never publish
it or install it on a workstation.
"""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package_dir', type=Path)
    parser.add_argument('version', help='Version of the current split .debs')
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    subprocess.run(['dpkg', '--validate-version', '1.0.0-15+splitfixture'], check=True)
    with tempfile.TemporaryDirectory(prefix='relay-legacy-fixture-') as directory:
        root = Path(directory)
        for suffix in ['', '-gnome', '-tray']:
            package = args.package_dir / f'gnome-wifi-hotspot{suffix}_{args.version}_all.deb'
            subprocess.run(['dpkg-deb', '-x', str(package), str(root)], check=True)
            if not suffix:
                subprocess.run(['dpkg-deb', '-e', str(package), str(root / 'DEBIAN')], check=True)
        control = root / 'DEBIAN/control'
        lines = control.read_text().splitlines()
        lines = ['Version: 1.0.0-15+splitfixture' if line.startswith('Version: ') else line
                 for line in lines if not line.startswith(('Suggests: ', 'Installed-Size: '))]
        control.write_text('\n'.join(lines) + '\n')
        (root / 'DEBIAN/preinst').unlink()
        for name in ['postinst', 'postrm']:
            path = root / 'DEBIAN' / name
            original = Path(__file__).resolve().parents[1] / 'packaging/debian' / name
            path.write_text(''.join(line for line in original.read_text().splitlines(True)
                                    if not line.startswith('dpkg-maintscript-helper rm_conffile ')))
        for name in ['gnome', 'tray']:
            (root / f'etc/xdg/autostart/wifi-relay-{name}.desktop').unlink()
            shutil.rmtree(root / f'usr/share/doc/gnome-wifi-hotspot-{name}')
        legacy = root / 'etc/xdg/autostart/wifi-hotspot-autostart.desktop'
        legacy.write_text('[Desktop Entry]\nType=Application\nName=Wi-Fi Relay Tray\n'
                          'Exec=wifi-hotspot-enable-extension\nTryExec=wifi-hotspot-enable-extension\n'
                          'NoDisplay=true\nX-GNOME-Autostart-enabled=true\n')
        (root / 'DEBIAN/conffiles').write_text(''.join('/' + str(path.relative_to(root)) + '\n'
                                                  for path in sorted((root / 'etc').rglob('*')) if path.is_file()))
        (root / 'DEBIAN/md5sums').unlink(missing_ok=True)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['dpkg-deb', '--root-owner-group', '--build', str(root), str(args.output)], check=True)


if __name__ == '__main__':
    main()
