import errno
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from campaign_simulation.lock import advisory_lock


class LockAdapterUnitTests(unittest.TestCase):
    def test_posix_retries_only_on_eagain_or_eacces(self):
        # Use a temporary directory to avoid leaving artifacts.
        with tempfile.TemporaryDirectory() as td:
            lockfile = Path(td) / "temp.lock"

            # Patch fcntl.flock to raise EAGAIN first, then succeed
            try:
                import fcntl  # type: ignore
            except Exception:
                self.skipTest("POSIX fcntl not available on this platform")

            def flock_side_effect(fd, op):
                # First call raises EAGAIN, subsequent calls succeed.
                if not hasattr(flock_side_effect, "called"):
                    flock_side_effect.called = True
                    raise OSError(errno.EAGAIN, "Resource temporarily unavailable")
                return None

            with patch("campaign_simulation.lock.fcntl.flock", side_effect=flock_side_effect):
                with advisory_lock(lockfile, timeout_seconds=1.0):
                    pass  # should acquire after retry

    def test_posix_propagates_unexpected_errno(self):
        with tempfile.TemporaryDirectory() as td:
            lockfile = Path(td) / "temp.lock"
            try:
                import fcntl  # type: ignore
            except Exception:
                self.skipTest("POSIX fcntl not available on this platform")

            def flock_side_effect(fd, op):
                raise OSError(errno.EINVAL, "Invalid argument")

            with patch("campaign_simulation.lock.fcntl.flock", side_effect=flock_side_effect):
                with self.assertRaises(OSError):
                    with advisory_lock(lockfile, timeout_seconds=0.1):
                        pass

    def test_windows_retries_only_on_locking_contention(self):
        # Use a temporary directory to avoid leaving artifacts.
        if os.name != "nt":
            self.skipTest("Windows locking not available on this platform")

        with tempfile.TemporaryDirectory() as td:
            lockfile = Path(td) / "temp.lock"

            # Patch msvcrt.locking to first raise a contention error (EACCES), then succeed.
            import msvcrt  # type: ignore

            def locking_side_effect(fd, mode, nbytes):
                if not hasattr(locking_side_effect, "called"):
                    locking_side_effect.called = True
                    raise OSError(errno.EACCES, "Lock violation")
                return None

            with patch("campaign_simulation.lock.msvcrt.locking", side_effect=locking_side_effect):
                with advisory_lock(lockfile, timeout_seconds=1.0):
                    pass

    def test_windows_propagates_unexpected_errors(self):
        if os.name != "nt":
            self.skipTest("Windows locking not available on this platform")

        with tempfile.TemporaryDirectory() as td:
            lockfile = Path(td) / "temp.lock"

            def locking_side_effect(fd, mode, nbytes):
                raise OSError(errno.EINVAL, "Invalid argument")

            with patch("campaign_simulation.lock.msvcrt.locking", side_effect=locking_side_effect):
                with self.assertRaises(OSError):
                    with advisory_lock(lockfile, timeout_seconds=0.1):
                        pass


if __name__ == "__main__":
    unittest.main()
