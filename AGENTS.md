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
