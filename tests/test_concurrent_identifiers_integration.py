import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# This test uses real subprocesses to verify concurrent allocation does not produce duplicates.

CHILD_SCRIPT = r'''
import json, sys
from pathlib import Path
from campaign_simulation.lifecycles import allocate_persistent_identifier

root = Path(sys.argv[1])
state_path = root / "runtime" / "session-state.json"
state_path.parent.mkdir(parents=True, exist_ok=True)
out = []
# allocate 50 identifiers
for _ in range(50):
    ident = allocate_persistent_identifier(state_path, "hook", lock_timeout=5.0)
    out.append(ident)
# write results
(Path(sys.argv[2])).write_text(json.dumps(out))
'''

class ConcurrentIdentifiersIntegrationTest(unittest.TestCase):
    def test_two_processes_no_duplicate_identifiers(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            out1 = Path(td) / "out1.json"
            out2 = Path(td) / "out2.json"
            # run two child processes concurrently, capture stderr for diagnostics
            p1 = subprocess.Popen([sys.executable, "-c", CHILD_SCRIPT, str(root), str(out1)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            p2 = subprocess.Popen([sys.executable, "-c", CHILD_SCRIPT, str(root), str(out2)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            rc1 = p1.wait(timeout=30)
            rc2 = p2.wait(timeout=30)

            stdout1, stderr1 = p1.communicate()
            stdout2, stderr2 = p2.communicate()

            # Assert both exited cleanly
            self.assertEqual(rc1, 0, f"process1 failed: rc={rc1}, stderr={stderr1.decode(errors='replace')}")
            self.assertEqual(rc2, 0, f"process2 failed: rc={rc2}, stderr={stderr2.decode(errors='replace')}")

            a = json.loads(out1.read_text())
            b = json.loads(out2.read_text())
            combined = a + b

            # Exactly 100 identifiers allocated
            self.assertEqual(len(combined), 100, f"expected 100 allocations, got {len(combined)}")

            # No duplicates
            self.assertEqual(len(set(combined)), 100, "duplicate identifiers detected")

            # identifiers must be exactly hook-000001 .. hook-000100 (order not guaranteed across processes)
            expected = [f"hook-{i:06d}" for i in range(1, 101)]
            # Sort combined by numeric part
            def key_fn(s: str) -> int:
                return int(s.split("-", 1)[1])
            combined_sorted = sorted(combined, key=key_fn)
            self.assertEqual(combined_sorted, expected, f"identifiers sequence mismatch: {combined_sorted[:5]}...")

            # Check final persisted counter
            state_path = root / "runtime" / "session-state.json"
            persisted = json.loads(state_path.read_text())
            final_counter = persisted.get("identifier_counters", {}).get("hook")
            self.assertEqual(final_counter, 101)  # started at 1, allocated 100 -> next value 101

if __name__ == "__main__":
    unittest.main()
