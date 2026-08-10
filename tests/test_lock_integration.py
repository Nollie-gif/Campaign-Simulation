import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from campaign_simulation.lock import advisory_lock

# Integration tests require real OS-level behavior; skip when running on unsupported CI or when subprocess usage is restricted.


def _child_python_code(lock_path_str: str, ready_path_str: str):
    # This string is executed by the child process.
    return f"""
import time
from pathlib import Path
from campaign_simulation.lock import advisory_lock
lock_path = Path({lock_path_str!r})
ready_path = Path({ready_path_str!r})
with advisory_lock(lock_path, timeout_seconds=5.0):
    # Signal the parent that lock was acquired
    ready_path.write_text("locked")
    # Sleep indefinitely until killed by parent
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
"""


class LockIntegrationTests(unittest.TestCase):
    def test_child_holds_lock_parent_acquires_after_kill(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            lock_path = root / "session-state.json.lock"
            ready_path = root / "child.ready"

            # Write a small script for the child to execute
            code = _child_python_code(str(lock_path), str(ready_path))
            child = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            try:
                # Wait for the child to signal it acquired the lock
                deadline = time.time() + 5.0
                while time.time() < deadline:
                    if ready_path.exists():
                        break
                    time.sleep(0.01)
                else:
                    self.fail("child did not signal lock acquisition in time")

                # Parent should fail to acquire lock quickly (short timeout shows contention)
                with self.assertRaises(RuntimeError):
                    # acquire with a small timeout to prove contention
                    from campaign_simulation.lock import advisory_lock as parent_advisory_lock
                    with parent_advisory_lock(lock_path, timeout_seconds=0.2):
                        pass

                # Kill the child without letting it clean up
                child.kill()
                child.wait(timeout=5.0)

                # Now parent should be able to acquire the lock within a bounded retry.
                acquired = False
                deadline = time.time() + 5.0
                while time.time() < deadline:
                    try:
                        with advisory_lock(lock_path, timeout_seconds=0.5):
                            acquired = True
                            break
                    except RuntimeError:
                        time.sleep(0.01)
                self.assertTrue(acquired, "parent failed to acquire lock after child termination")

                # Verify persistent lock file still exists and was not deleted by the adapter.
                self.assertTrue(lock_path.exists())
            finally:
                try:
                    child.kill()
                except Exception:
                    pass


if __name__ == "__main__":
    unittest.main()
