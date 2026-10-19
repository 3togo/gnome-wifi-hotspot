#!/usr/bin/python3
"""One bounded administrator login for prepared physical-test scripts and retries."""
import argparse
import json
import math
import os
from pathlib import Path
import select
import signal
import stat
import subprocess
import sys
import time


def script_path(bench, name, uid):
    if not isinstance(name, str) or Path(name).name != name or not name.endswith('.py'):
        raise ValueError('Use a Python filename inside the private bench directory.')
    path = bench / name
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid not in {uid, 0}
            or info.st_mode & 0o022):
        raise ValueError('Test scripts must be owned by the operator or root and not publicly writable.')
    return path


def stop_job(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def run_job(path, timeout):
    process = subprocess.Popen(['/usr/bin/python3', '-I', '-u', str(path)],
                               cwd=path.parent, stdin=subprocess.DEVNULL,
                               start_new_session=True)
    try:
        return process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        stop_job(process)
        return 124
    except BaseException:
        stop_job(process)
        raise


def requests(stream, deadline):
    """Read bounded lines without hiding buffered requests from select()."""
    pending = b''
    while time.monotonic() < deadline:
        if b'\n' in pending:
            line, pending = pending.split(b'\n', 1)
            if len(line) > 4096:
                raise ValueError('Administrator request exceeds 4096 bytes.')
            yield line.decode('utf-8')
            continue
        if len(pending) > 4096:
            raise ValueError('Administrator request exceeds 4096 bytes.')
        if not select.select([stream], [], [], max(0, deadline - time.monotonic()))[0]:
            return
        data = os.read(stream.fileno(), 4096)
        if not data:
            return
        pending += data


def session(bench, allowed, cleanup, uid, deadline, incoming, emit):
    restored = False
    def restore():
        code = run_job(script_path(bench, cleanup, uid), 120)
        emit({'event': 'cleanup', 'returncode': code})
        if code:
            raise RuntimeError('Physical-test restoration failed; inspect the cleanup output.')
    try:
        emit({'event': 'ready', 'allowed': sorted(allowed)})
        for line in incoming:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                request = json.loads(line)
                if request == {'finish': True}:
                    break
                if not isinstance(request, dict) or set(request) - {'script', 'timeout'}:
                    raise ValueError('Use script and optional timeout, or finish.')
                name = request.get('script')
                if not isinstance(name, str) or name not in allowed:
                    raise ValueError('That script was not approved when this session started.')
                timeout = request.get('timeout', 300)
                if (type(timeout) not in {int, float} or not math.isfinite(timeout)
                        or timeout <= 0):
                    raise ValueError('Timeout must be a positive finite number of seconds.')
                path = script_path(bench, name, uid)
            except (ValueError, OSError) as exc:
                emit({'event': 'rejected', 'reason': str(exc)})
                continue
            restored = False
            code = run_job(path, min(timeout, remaining))
            emit({'event': 'result', 'script': name, 'returncode': code})
            if code:
                restore()
                restored = True
    finally:
        # The prepared restoration script is separate from mutable trial code.
        # It must be idempotent and also verify restoration after interrupted jobs.
        if not restored:
            restore()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bench', type=Path, required=True)
    parser.add_argument('--allow', action='append', required=True, help='Prepared script filename; repeat as needed')
    parser.add_argument('--cleanup', required=True, help='Prepared, idempotent restoration script filename')
    parser.add_argument('--seconds', type=int, default=1800, help='Session lifetime, 60–3600 seconds; default 1800')
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if not 60 <= args.seconds <= 3600:
        parser.error('Session lifetime must be between 60 and 3600 seconds.')
    if args.worker:
        if os.geteuid() != 0 or not os.environ.get('PKEXEC_UID', '').isdigit():
            parser.error('The administrator worker must be launched through pkexec.')
        uid = int(os.environ['PKEXEC_UID'])
    else:
        uid = os.getuid()
    bench = args.bench.resolve(strict=True)
    info = bench.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != uid or stat.S_IMODE(info.st_mode) != 0o700:
        parser.error('Use an operator-owned bench directory with mode 0700.')
    for name in [*args.allow, args.cleanup]:
        script_path(bench, name, uid)
    if not args.worker:
        command = ['/usr/bin/pkexec', '/usr/bin/python3', '-I', '-u', str(Path(__file__).resolve()),
                   '--worker', '--bench', str(bench), '--cleanup', args.cleanup,
                   '--seconds', str(args.seconds)]
        for name in args.allow:
            command.extend(['--allow', name])
        os.execv(command[0], command)
    os.umask(0o077)
    def interrupted(_signal, _frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    deadline = time.monotonic() + args.seconds
    def emit(message):
        print('admin-session ' + json.dumps(message), flush=True)
    session(bench, set(args.allow), args.cleanup, uid, deadline,
            requests(sys.stdin, deadline), emit)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
