"""Guard rails for the KIA persona: identity, honest capabilities, reporting standards."""

from brain_core.persona import KIA_SYSTEM


class TestPersonaInvariants:
    """These phrases are load-bearing; losing them regresses user-facing behavior."""

    def test_identifies_as_kia(self) -> None:
        assert "You are KIA" in KIA_SYSTEM

    def test_bans_false_llm_disclaimers(self) -> None:
        assert "Do NOT recite generic" in KIA_SYSTEM
        assert "fixed knowledge cutoff" in KIA_SYSTEM

    def test_bans_fabricated_tool_output(self) -> None:
        assert "Do not fabricate tool" in KIA_SYSTEM

    def test_requires_outcome_first_communication(self) -> None:
        assert "Lead with the outcome" in KIA_SYSTEM

    def test_requires_faithful_outcome_reporting(self) -> None:
        assert "Report outcomes faithfully" in KIA_SYSTEM
        assert "Verify before claiming" in KIA_SYSTEM

    def test_bans_promises_of_future_work(self) -> None:
        assert "Never promise future work" in KIA_SYSTEM
