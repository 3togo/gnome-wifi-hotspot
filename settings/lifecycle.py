"""Detect desktop-code upgrades and removals without depending on GTK."""
import time


class CodeRevision:
    def __init__(self, paths):
        self.paths = tuple(paths)
        self.initial = self._snapshot()
        self._missing_since = None

    def _snapshot(self):
        try:
            return tuple((path.stat().st_ino, path.stat().st_mtime_ns, path.stat().st_size)
                         for path in self.paths)
        except OSError:
            return None

    def changed(self):
        current = self._snapshot()
        # An upgrade can briefly remove a file; wait for the complete set.
        return self.initial is not None and current is not None and current != self.initial

    def removed(self, now=None, grace_seconds=10):
        """Allow brief upgrade gaps, then exit a removed desktop integration."""
        now = time.monotonic() if now is None else now
        if self._snapshot() is not None:
            self._missing_since = None
            return False
        if self._missing_since is None:
            self._missing_since = now
        return now - self._missing_since >= grace_seconds
