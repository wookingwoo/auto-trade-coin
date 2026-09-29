import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from jevbot.store import Journal


class JournalTests(unittest.TestCase):
    def test_initial_capital_and_halt_survive_reopen_and_new_day(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "state.db"
            journal = Journal(path)
            journal.initialize(Decimal("1000"), "2026-09-29")
            journal.halt("daily_loss")
            journal.close()

            restored = Journal(path)
            restored.initialize(Decimal("5000"), "2026-09-30")
            self.assertEqual(restored.get_decimal("initial_equity"), Decimal("1000"))
            self.assertEqual(restored.get("halt_reason"), "daily_loss")
            restored.close()

    def test_same_slot_has_only_one_persisted_entry_intent(self):
        with tempfile.TemporaryDirectory() as folder:
            journal = Journal(Path(folder) / "state.db")
            self.assertTrue(journal.begin_intent("live:v1:BTCUSDT:100:e", "jv-entry", "BTCUSDT", "LONG", "0.01", "49000", "52000"))
            self.assertFalse(journal.begin_intent("live:v1:BTCUSDT:100:e", "jv-other", "BTCUSDT", "LONG", "0.01", "49000", "52000"))
            self.assertEqual(journal.intent("live:v1:BTCUSDT:100:e")["client_id"], "jv-entry")
            journal.close()

    def test_environment_binding_rejects_paper_database_in_live_mode(self):
        with tempfile.TemporaryDirectory() as folder:
            journal = Journal(Path(folder) / "state.db")
            journal.bind_environment("paper")
            journal.initialize(Decimal("700"), "2026-09-29")
            with self.assertRaises(ValueError):
                journal.bind_environment("live")
            self.assertEqual(journal.get_decimal("initial_equity"), Decimal("700"))
            journal.close()


if __name__ == "__main__":
    unittest.main()
