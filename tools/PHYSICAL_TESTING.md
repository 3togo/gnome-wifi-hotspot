# One administrator login per physical test session

Prepare packages, test scripts, backups, and restoration steps before requesting
administrator authentication. Keep builds, unit tests, GTK checks, and ordinary
ADB operations in the normal user session.

Use `physical_admin_session.py` for the steps that need root. It requests
authentication once through Polkit, then runs only the script filenames approved
at startup, in the same administrator process. Trials can fail, be corrected and
be retried without another authentication request during that session. It does
not save passwords, modify sudo policy, or install a background service.

Create a private bench directory with mode `0700`. Prepare and review the scripts
there before launching the session. Scripts must be regular files, owned by the
operator or root, without group or other write permission. The cleanup script
must restore saved packages, configuration, networking and preferences, remove
temporary device helpers, and verify restoration. It must be safe to run after a
partially completed trial and when no trial has run. Keep the Android wake monitor
running until restoration and final verification finish.

Start once in a retained terminal or Codex execution session:

```sh
python3 tools/physical_admin_session.py \
  --bench /absolute/path/to/private-bench \
  --allow trial.py --allow audit.py --cleanup restore.py --seconds 1800
```

After the `ready` event, send newline-delimited requests through that same
session's standard input:

```json
{"script":"trial.py","timeout":300}
{"script":"audit.py","timeout":30}
{"finish":true}
```

For Codex, retain the `exec_command` session with `tty: true` and send requests
with `write_stdin`. Do not start another `pkexec` for a retry or final audit.
The operator enters their password in the system authentication prompt, never
in chat or a tool argument. A `sudo -v` in a different terminal is not a reliable
substitute because its authentication cache may be tied to that terminal.

Observe each job's `result` return code. A failed or timed-out job runs restoration
before accepting another trial, keeping the session open for correction and retry.
Jobs use isolated Python with
standard input disconnected; import any bench helpers through explicit paths.
The deadline includes active jobs and idle time, defaults to 30 minutes and is
capped at one hour. Expiry stops the current job and ends the session. EOF,
`finish`, interruption and timeout all run the prepared restoration script, with
a separate 120-second budget per restoration attempt. A nonzero cleanup result is reported as an
error requiring investigation. Close the session after final verification;
a later session can require authentication again.

Keep raw output private and append sanitized candidate-specific evidence. Do not
replace earlier failures with successful retry results. This helper coordinates
prepared scripts; it does not supply a hardware test plan or infer restoration
steps for the bench.
