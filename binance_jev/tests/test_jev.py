import unittest
from types import SimpleNamespace

from jevbot.jev import Decision, JevDecider, gate_decision


class FakeClient:
    def __init__(self, answer=None, error=None):
        self.answer = answer
        self.error = error
        self.calls = []

    def system_one(self, state, questions, **kwargs):
        self.calls.append((state, questions, kwargs))
        if self.error:
            raise self.error
        return SimpleNamespace(choices={"action": self.answer}, model="jev-1.13.0", request_id="rid")


class JevTests(unittest.TestCase):
    def test_entry_needs_probability_and_margin(self):
        self.assertEqual(gate_decision(Decision("OPEN_LONG", {"OPEN_LONG": .65, "WAIT": .25, "OPEN_SHORT": .10}, .8), False), "OPEN_LONG")
        self.assertEqual(gate_decision(Decision("OPEN_LONG", {"OPEN_LONG": .64, "WAIT": .2, "OPEN_SHORT": .16}, .8), False), "WAIT")
        self.assertEqual(gate_decision(Decision("OPEN_LONG", {"OPEN_LONG": .65, "WAIT": .3, "OPEN_SHORT": .05}, .8), False), "OPEN_LONG")
        self.assertEqual(gate_decision(Decision("OPEN_LONG", {"OPEN_LONG": .65, "WAIT": .36, "OPEN_SHORT": .35}, .8), False), "WAIT")

    def test_close_requires_its_own_threshold(self):
        self.assertEqual(gate_decision(Decision("CLOSE", {"CLOSE": .61, "KEEP": .39}, .7), True), "CLOSE")
        self.assertEqual(gate_decision(Decision("CLOSE", {"CLOSE": .59, "KEEP": .41}, .7), True), "KEEP")

    def test_sdk_choice_request_is_constrained_to_position_state(self):
        client = FakeClient(SimpleNamespace(choice="WAIT", probabilities={"WAIT": .8, "OPEN_LONG": .1, "OPEN_SHORT": .1}, confidence=.7))
        decision = JevDecider(client=client).decide({"5m": {"close": 100}}, held=False)
        self.assertEqual(decision.action, "WAIT")
        self.assertEqual(set(client.calls[0][1]["action"]["criteria"]), {"WAIT", "OPEN_LONG", "OPEN_SHORT"})
        self.assertEqual(client.calls[0][2]["model"], "jev-1.13.0")

    def test_bad_response_and_api_error_fail_closed(self):
        bad = FakeClient(SimpleNamespace(choice="OPEN_LONG", probabilities={"WAIT": .1, "OPEN_LONG": .9}, confidence=.8))
        self.assertEqual(JevDecider(client=bad).decide({}, held=False).action, "WAIT")
        failed = FakeClient(error=TimeoutError("secret detail"))
        self.assertEqual(JevDecider(client=failed).decide({}, held=True).action, "KEEP")


if __name__ == "__main__":
    unittest.main()
