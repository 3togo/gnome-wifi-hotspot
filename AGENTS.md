# Android hardware validation

When an Android device is available over ADB for Wi-Fi Relay testing, keeping
the phone awake and unlocked during the test is the agent's responsibility.
Do not ask the user to repeatedly wake the phone or keep its screen on.

- Select the intended device explicitly with `adb -s DEVICE`.
- Record the existing `settings get global stay_on_while_plugged_in` value before
  changing it. Use `svc power stayon true` for the test and wake the display with
  `input keyevent KEYCODE_WAKEUP` as needed. Stay-awake applies while powered;
  verify the device stays awake and use wake events during active testing if needed.
- An existing secure screen lock may still require the user to unlock once;
  do not disable credentials or bypass the secure lock.
- Restore the previous stay-awake setting when testing ends and remove any
  temporary test helpers pushed to the phone.
- Prefer USB ADB when switching the phone between upstream Wi-Fi and the hotspot,
  since wireless ADB may disconnect during the switch.

# Administrator authentication during physical tests

- Prepare builds, trials, backups and idempotent restoration before requesting
  authentication. Run ordinary builds, automated tests and ADB as the normal user.
- Use one bounded administrator session for the physical test, including retries
  and the final audit. Prefer `tools/physical_admin_session.py`; follow
  `tools/PHYSICAL_TESTING.md` and retain its execution session across rebuilds.
- Do not launch a fresh `pkexec` for each trial or ask for `sudo -v` in a different
  terminal. Do not store passwords or weaken sudo/Polkit policy to avoid prompts.
- Finish the session after cleanup and verification. Authenticate again only
  when the previous session has ended or authorization is no longer available.
