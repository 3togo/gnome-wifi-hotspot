"""Detect complete desktop-code upgrades without depending on GTK."""
class CodeRevision:
    def __init__(self, paths):
        self.paths = tuple(paths)
        self.initial = self._snapshot()

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
