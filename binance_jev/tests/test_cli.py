import tempfile
import unittest
from pathlib import Path

from jevbot.main import apply_control
from jevbot.store import Journal


class ControlTests(unittest.TestCase):
    def test_resume_does_not_clear_loss_halt(self):
        with tempfile.TemporaryDirectory() as folder:
            journal = Journal(Path(folder) / "state.db")
            journal.halt("loss_limit")
            apply_control(journal, "pause")
            apply_control(journal, "resume")
            self.assertEqual(journal.get("paused"), "0")
            self.assertEqual(journal.get("halt_reason"), "loss_limit")
            journal.close()

    def test_flatten_command_is_persisted_for_runner(self):
        with tempfile.TemporaryDirectory() as folder:
            journal = Journal(Path(folder) / "state.db")
            apply_control(journal, "flatten-and-halt")
            self.assertEqual(journal.get("command"), "flatten_and_halt")
            journal.close()


if __name__ == "__main__":
    unittest.main()
