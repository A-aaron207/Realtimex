"""
Regression test — Audit Finding: Hardcoded Autonomous Plan Repair Mocks.

Before fix (Architecture Audit Finding #8 — MEDIUM):
    _on_step_failed() in kernel/core.py contained a keyword-sniffing block
    that overwrote the real LLM response with a static hardcoded plan whenever
    the task goal contained words like "repair", "plan repair", or "permanent failure".
    This meant ANY production task with these words in the goal would receive a
    fake single-step write_file plan instead of a dynamically constructed repair.

    The hardcoded block was:
        if raw_output.startswith("Simulated") or "repair" in task.goal.lower() ...:
            raw_output = json.dumps({"intent": "recovery_success", ...})

After fix:
    The mock override block is completely removed.
    The LLM output is used directly in all cases.
    Malformed/empty output is already handled by the existing JSON extraction
    and capability-validation fallback (lines ~980-1028 in the original file).

Bug: Architecture Audit Finding #8 (Hardcoded Autonomous Plan Repair Mocks)
"""

import inspect
import unittest


class TestPlanRepairNoHardcodedMock(unittest.TestCase):
    """Verify the hardcoded mock override was removed from _on_step_failed."""

    def _get_source(self) -> str:
        import kernel.core as core_module
        return inspect.getsource(core_module.Kernel._on_step_failed)

    def test_no_simulated_keyword_check(self):
        """The mock override that checked raw_output.startswith('Simulated') must be gone."""
        source = self._get_source()
        self.assertNotIn(
            "startswith(\"Simulated\")",
            source,
            "_on_step_failed must not check for 'Simulated' prefix to override LLM output.",
        )

    def test_no_goal_keyword_sniffing(self):
        """
        The mock override that sniffed task.goal.lower() for keywords
        ('permanent failure', 'plan repair', 'repair') to force a fake plan must be gone.

        Note: 'repair' still legitimately appears in log strings and prompt text —
        we only check for the specific goal.lower() sniffing patterns.
        """
        source = self._get_source()
        self.assertNotIn(
            "permanent failure\" in task.goal.lower()",
            source,
            "_on_step_failed must not sniff 'permanent failure' in task.goal.",
        )
        self.assertNotIn(
            "plan repair\" in task.goal.lower()",
            source,
            "_on_step_failed must not sniff 'plan repair' in task.goal to force a mock.",
        )
        self.assertNotIn(
            "\"repair\" in task.goal.lower()",
            source,
            "_on_step_failed must not override LLM output when goal contains 'repair'.",
        )

    def test_no_recovery_success_hardcode(self):
        """
        The hardcoded 'recovery_success' intent override block must not exist.
        recovery_success may still be used as an LLM-returned intent (that's fine),
        but the explicit mock assignment must be gone.
        """
        source = self._get_source()
        # The specific pattern was: raw_output = json.dumps({"intent": "recovery_success", ...})
        # inside the keyword-sniffing if-block. Check that literal assignment is gone.
        self.assertNotIn(
            "raw_output = json.dumps({",
            source,
            "_on_step_failed must not reassign raw_output with a hardcoded json.dumps().",
        )

    def test_llm_output_path_still_present(self):
        """The LLM call and raw_output strip() must still be present — we're not removing the whole flow."""
        source = self._get_source()
        self.assertIn(
            "raw_output = response.output.strip()",
            source,
            "LLM output extraction must still exist in _on_step_failed.",
        )

    def test_json_cleaning_still_present(self):
        """The legitimate JSON fence-cleaning code must still be present."""
        source = self._get_source()
        self.assertIn(
            "```json",
            source,
            "JSON markdown fence cleaning must still exist after mock removal.",
        )

    def test_capability_validation_fallback_still_present(self):
        """The legitimate capability-validation fallback must still be present."""
        source = self._get_source()
        self.assertIn(
            "filtered_caps",
            source,
            "Capability validation / filtering of LLM-suggested caps must still exist.",
        )


if __name__ == "__main__":
    unittest.main()
