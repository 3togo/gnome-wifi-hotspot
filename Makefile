SHELL := /bin/bash
UUID := wifi-relay@3togo.github.io
EXT_DIR := $(HOME)/.local/share/gnome-shell/extensions/$(UUID)
SRC_EXT_DIR := $(PWD)/extension
DBUS_CONF := $(PWD)/data/io.github.erhanzeyrek.WifiHotspot.conf
POLKIT_RULES := $(PWD)/data/io.github.erhanzeyrek.WifiHotspot.rules
POLKIT_POLICY := $(PWD)/data/io.github.erhanzeyrek.WifiHotspot.policy
SYSTEM_CONFIG := $(PWD)/data/wifi-hotspot.conf

.PHONY: all dev-setup dev-run-daemon dev-run-shell dev-watch-shell dev-run-settings dev-test-dbus dev-monitor-dbus dev-clean install uninstall test test-nm-menu

test:
	python3 -m unittest discover -s tests
	node tests/test_tray.mjs

test-nm-menu:
	integration/nm-applet/test.sh

all:
	@echo "Wi-Fi Relay"
	@echo "Targets:"
	@echo "  dev-setup         - Set up symlinks, D-Bus policy, and Polkit rules for live development (no reboot)"
	@echo "  dev-run-daemon    - Run D-Bus daemon in foreground (terminal 1)"
	@echo "  dev-run-shell     - Launch nested GNOME Shell instance (terminal 2)"
	@echo "  dev-watch-shell   - Watch extension files and auto-restart nested GNOME Shell on save"
	@echo "  dev-run-settings  - Launch Libadwaita settings application"
	@echo "  dev-test-dbus     - Call D-Bus GetStatus method"
	@echo "  dev-monitor-dbus  - Monitor live D-Bus traffic"
	@echo "  dev-clean         - Remove dev symlinks and /etc configs"
	@echo "  install           - Install to system (/usr/local or root)"
	@echo "  uninstall         - Uninstall from system"

dev-setup:
	@echo "==> Setting up GNOME Shell extension symlink..."
	@mkdir -p $(HOME)/.local/share/gnome-shell/extensions
	@ln -sfn $(SRC_EXT_DIR) $(EXT_DIR)
	@echo "==> Installing D-Bus system policy to /etc/dbus-1/system.d/..."
	@sudo cp $(DBUS_CONF) /etc/dbus-1/system.d/
	@sudo systemctl reload dbus 2>/dev/null || sudo busctl call org.freedesktop.DBus /org/freedesktop/DBus org.freedesktop.DBus ReloadConfig 2>/dev/null || true
	@echo "==> Installing Polkit rule to /etc/polkit-1/rules.d/..."
	@sudo cp $(POLKIT_RULES) /etc/polkit-1/rules.d/
	@echo "==> Setting up default config at /etc/wifi-hotspot.conf..."
	@if [ ! -f /etc/wifi-hotspot.conf ]; then sudo cp $(SYSTEM_CONFIG) /etc/wifi-hotspot.conf; fi
	@echo "==> Setup complete! You can now run 'make dev-run-daemon' and 'make dev-run-shell'."

dev-service-enable:
	@echo "==> Creating and enabling systemd development service..."
	@echo "[Unit]" | sudo tee /etc/systemd/system/wifi-hotspot-daemon.service > /dev/null
	@echo "Description=Wi-Fi Relay D-Bus Daemon (Dev)" | sudo tee -a /etc/systemd/system/wifi-hotspot-daemon.service > /dev/null
	@echo "After=network.target" | sudo tee -a /etc/systemd/system/wifi-hotspot-daemon.service > /dev/null
	@echo "[Service]" | sudo tee -a /etc/systemd/system/wifi-hotspot-daemon.service > /dev/null
	@echo "Type=dbus" | sudo tee -a /etc/systemd/system/wifi-hotspot-daemon.service > /dev/null
	@echo "BusName=io.github.erhanzeyrek.WifiHotspot" | sudo tee -a /etc/systemd/system/wifi-hotspot-daemon.service > /dev/null
	@echo "ExecStart=/usr/bin/python3 $(PWD)/daemon/wifi-hotspot-daemon.py" | sudo tee -a /etc/systemd/system/wifi-hotspot-daemon.service > /dev/null
	@echo "Restart=on-failure" | sudo tee -a /etc/systemd/system/wifi-hotspot-daemon.service > /dev/null
	@echo "RestartSec=2" | sudo tee -a /etc/systemd/system/wifi-hotspot-daemon.service > /dev/null
	@echo "[Install]" | sudo tee -a /etc/systemd/system/wifi-hotspot-daemon.service > /dev/null
	@echo "WantedBy=multi-user.target" | sudo tee -a /etc/systemd/system/wifi-hotspot-daemon.service > /dev/null
	@sudo systemctl daemon-reload
	@sudo systemctl enable --now wifi-hotspot-daemon.service
	@echo "==> Service enabled and running in background!"

dev-service-status:
	@sudo systemctl status wifi-hotspot-daemon.service

dev-service-logs:
	@journalctl -u wifi-hotspot-daemon.service -f -n 50

dev-run-daemon:
	@echo "==> Starting Wi-Fi Hotspot D-Bus daemon in foreground..."
	sudo python3 daemon/wifi-hotspot-daemon.py

dev-enable:
	@echo "==> Enabling extension in current session..."
	gnome-extensions enable $(UUID)

dev-disable:
	@echo "==> Disabling extension in current session..."
	gnome-extensions disable $(UUID)

dev-reload: dev-disable dev-enable
	@echo "==> Extension reloaded in current session."

dev-run-shell:
	@echo "==> Launching nested GNOME Shell (Wayland)..."
	MUTTER_DEBUG_DUMMY_MODE_SPECS="1440x900@60.0" gnome-shell --wayland --no-x11

dev-watch-shell:
	@echo "==> Watching extension/ files with entr for auto-restarts..."
	find $(SRC_EXT_DIR) -type f \( -name "*.js" -o -name "*.css" -o -name "*.json" \) | \
	entr -r -s 'MUTTER_DEBUG_DUMMY_MODE_SPECS="1440x900@60.0" gnome-shell --wayland --no-x11'

dev-run-settings:
	@echo "==> Launching Settings UI..."
	python3 settings/main.py

dev-test-dbus:
	@echo "==> Querying D-Bus GetStatus..."
	gdbus call --system \
	  --dest io.github.erhanzeyrek.WifiHotspot \
	  --object-path /io/github/erhanzeyrek/WifiHotspot \
	  --method io.github.erhanzeyrek.WifiHotspot.GetStatus

dev-monitor-dbus:
	@echo "==> Monitoring D-Bus traffic for io.github.erhanzeyrek.WifiHotspot..."
	busctl --system monitor io.github.erhanzeyrek.WifiHotspot

dev-clean:
	@echo "==> Cleaning development files..."
	@rm -f $(EXT_DIR)
	@sudo rm -f /etc/dbus-1/system.d/io.github.erhanzeyrek.WifiHotspot.conf
	@sudo rm -f /etc/polkit-1/rules.d/io.github.erhanzeyrek.WifiHotspot.rules
	@sudo systemctl reload dbus 2>/dev/null || true
	@echo "==> Cleanup complete."

install:
PREFIX ?= /usr/local
SYSCONFDIR ?= /etc

install:
	@echo "==> Installing system components to $(PREFIX)..."
	install -d -m 0755 $(PREFIX)/share/gnome-shell/extensions/$(UUID)
	cp -r extension/* $(PREFIX)/share/gnome-shell/extensions/$(UUID)/
	install -d -m 0755 $(PREFIX)/libexec/wifi-hotspot-daemon
	install -m 0755 daemon/wifi-hotspot-daemon.py $(PREFIX)/libexec/wifi-hotspot-daemon/
	install -m 0755 daemon/create_ap $(PREFIX)/libexec/wifi-hotspot-daemon/
	install -m 0755 daemon/nm_backend.py $(PREFIX)/libexec/wifi-hotspot-daemon/
	install -m 0644 daemon/configuration.py $(PREFIX)/libexec/wifi-hotspot-daemon/
	install -d -m 0755 $(PREFIX)/libexec/wifi-hotspot-daemon/tools
	install -m 0755 tools/nm_ap_sta_probe.py $(PREFIX)/libexec/wifi-hotspot-daemon/tools/
	install -d -m 0755 $(PREFIX)/share/wifi-hotspot/settings
	install -m 0755 settings/main.py settings/enable-extension.py settings/tray.py $(PREFIX)/share/wifi-hotspot/settings/
	install -m 0644 settings/startup.py settings/visibility.py settings/preferences.py settings/lifecycle.py settings/service_client.py settings/wifi_qr.py settings/qrcodegen.py $(PREFIX)/share/wifi-hotspot/settings/
	cp -r settings/icons $(PREFIX)/share/wifi-hotspot/settings/
	install -d -m 0755 $(PREFIX)/bin
	ln -sf $(PREFIX)/share/wifi-hotspot/settings/main.py $(PREFIX)/bin/wifi-hotspot-settings
	ln -sf $(PREFIX)/share/wifi-hotspot/settings/enable-extension.py $(PREFIX)/bin/wifi-hotspot-enable-extension
	ln -sf $(PREFIX)/libexec/wifi-hotspot-daemon/tools/nm_ap_sta_probe.py $(PREFIX)/bin/wifi-relay-nm-probe
	install -d -m 0755 $(SYSCONFDIR)/xdg/autostart
	install -m 0644 data/wifi-hotspot-autostart.desktop $(SYSCONFDIR)/xdg/autostart/
	install -d -m 0755 $(SYSCONFDIR)/dbus-1/system.d
	install -m 0644 data/io.github.erhanzeyrek.WifiHotspot.conf $(SYSCONFDIR)/dbus-1/system.d/
	install -d -m 0755 $(PREFIX)/share/dbus-1/system-services
	sed "s|/usr/libexec|$(PREFIX)/libexec|g" data/io.github.erhanzeyrek.WifiHotspot.dbus-service > /tmp/dbus.service
	install -m 0644 /tmp/dbus.service $(PREFIX)/share/dbus-1/system-services/io.github.erhanzeyrek.WifiHotspot.service
	install -d -m 0755 $(PREFIX)/share/polkit-1/actions
	install -m 0644 data/io.github.erhanzeyrek.WifiHotspot.policy $(PREFIX)/share/polkit-1/actions/
	install -d -m 0755 $(SYSCONFDIR)/polkit-1/rules.d
	install -m 0644 data/io.github.erhanzeyrek.WifiHotspot.rules $(SYSCONFDIR)/polkit-1/rules.d/
	install -d -m 0755 $(SYSCONFDIR)/systemd/system
	sed "s|/usr/libexec|$(PREFIX)/libexec|g" data/wifi-hotspot-daemon.service > /tmp/systemd.service
	install -m 0644 /tmp/systemd.service $(SYSCONFDIR)/systemd/system/wifi-hotspot-daemon.service
	if [ ! -f $(SYSCONFDIR)/wifi-hotspot.conf ]; then \
		install -m 0600 data/wifi-hotspot.conf $(SYSCONFDIR)/wifi-hotspot.conf; \
		HOST=$$(hostname 2>/dev/null || echo "Hotspot"); \
		[ "$$HOST" = "localhost" ] && HOST="Hotspot"; \
		python3 daemon/configuration.py $(SYSCONFDIR)/wifi-hotspot.conf data/wifi-hotspot.conf --ssid "$${HOST}-Hotspot"; \
	fi
	chmod 0600 $(SYSCONFDIR)/wifi-hotspot.conf
	install -d -m 0755 $(PREFIX)/share/applications
	install -m 0644 data/io.github.erhanzeyrek.WifiHotspot.desktop $(PREFIX)/share/applications/
	install -d -m 0755 $(PREFIX)/share/metainfo
	install -m 0644 data/io.github.erhanzeyrek.WifiHotspot.metainfo.xml $(PREFIX)/share/metainfo/
	install -d -m 0755 $(PREFIX)/share/icons/hicolor/scalable/apps
	install -m 0644 data/icons/hotspot.svg $(PREFIX)/share/icons/hicolor/scalable/apps/io.github.erhanzeyrek.WifiHotspot.svg
	systemctl daemon-reload 2>/dev/null || true
	systemctl reload dbus 2>/dev/null || true
	systemctl enable wifi-hotspot-daemon.service 2>/dev/null || true

uninstall:
	@echo "==> Uninstalling system components from $(PREFIX)..."
	rm -rf $(PREFIX)/share/gnome-shell/extensions/$(UUID)
	rm -rf $(PREFIX)/libexec/wifi-hotspot-daemon
	rm -rf $(PREFIX)/share/wifi-hotspot
	rm -f $(PREFIX)/bin/wifi-hotspot-settings $(PREFIX)/bin/wifi-hotspot-enable-extension
	rm -f $(PREFIX)/bin/wifi-relay-nm-probe
	rm -f $(SYSCONFDIR)/xdg/autostart/wifi-hotspot-autostart.desktop
	rm -f $(SYSCONFDIR)/dbus-1/system.d/io.github.erhanzeyrek.WifiHotspot.conf
	rm -f $(PREFIX)/share/dbus-1/system-services/io.github.erhanzeyrek.WifiHotspot.service
	rm -f $(PREFIX)/share/polkit-1/actions/io.github.erhanzeyrek.WifiHotspot.policy
	rm -f $(SYSCONFDIR)/polkit-1/rules.d/io.github.erhanzeyrek.WifiHotspot.rules
	rm -f $(SYSCONFDIR)/systemd/system/wifi-hotspot-daemon.service
	rm -f $(PREFIX)/share/applications/io.github.erhanzeyrek.WifiHotspot.desktop
	rm -f $(PREFIX)/share/metainfo/io.github.erhanzeyrek.WifiHotspot.metainfo.xml
	rm -f $(PREFIX)/share/icons/hicolor/scalable/apps/io.github.erhanzeyrek.WifiHotspot.svg
	systemctl daemon-reload 2>/dev/null || true
	systemctl reload dbus 2>/dev/null || true
