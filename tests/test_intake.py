"""Intake tests. No network: a fake client returns canned model output."""

from dataclasses import dataclass
from typing import Any

import pytest

from casesupport.intake import (
    FieldExplanation,
    IntakeUnavailable,
    TranslatedAnswer,
    explain_field,
    render_answer,
)


@dataclass
class FakeResponse:
    parsed_output: Any
    stop_reason: str = "end_turn"
    stop_details: Any = None


class FakeMessages:
    def __init__(self, response):
        self._response = response
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return self._response


class FakeClient:
    def __init__(self, response):
        self.messages = FakeMessages(response)


def test_answer_translation_keeps_the_original_verbatim():
    original = "زه په ۲۰۱۹ کال کې راغلم"
    client = FakeClient(
        FakeResponse(
            TranslatedAnswer(
                english="I arrived in 2019.", translator_notes="Year given without a month."
            )
        )
    )
    answer = render_answer("part2_q5", original, "ps", client=client)

    # Both languages survive into the record; the original is untouched.
    assert answer.original_text == original
    assert answer.original_language == "ps"
    assert answer.english_text == "I arrived in 2019."
    assert answer.translator_notes == "Year given without a month."


def test_refusal_raises_instead_of_crashing_on_none():
    client = FakeClient(FakeResponse(parsed_output=None, stop_reason="refusal"))
    with pytest.raises(IntakeUnavailable, match="declined"):
        render_answer("part2_q5", "text", "ps", client=client)
    with pytest.raises(IntakeUnavailable, match="declined"):
        explain_field("Date of entry", "Enter the date you last entered.", "ps", client=client)


def test_empty_response_raises_rather_than_returning_none():
    client = FakeClient(FakeResponse(parsed_output=None))
    with pytest.raises(IntakeUnavailable, match="no usable response"):
        explain_field("Date of entry", "Enter the date.", "ps", client=client)


def test_explanation_can_flag_that_a_field_needs_a_lawyer():
    client = FakeClient(
        FakeResponse(
            FieldExplanation(
                explanation="...",
                answer_type="narrative",
                needs_legal_advice=True,
            )
        )
    )
    result = explain_field("Basis of claim", "Describe why you fear return.", "ps", client=client)
    assert result.needs_legal_advice is True


def test_translation_prompt_forbids_improving_the_answer():
    client = FakeClient(FakeResponse(TranslatedAnswer(english="x")))
    render_answer("q", "text", "ps", client=client)
    system = client.messages.calls[0]["system"].lower()
    for rule in ("do not smooth", "add nothing the applicant did not say", "faithfully"):
        assert rule in system


def test_explanation_prompt_forbids_coaching():
    client = FakeClient(FakeResponse(FieldExplanation(explanation="x", answer_type="date")))
    explain_field("q", "help", "ps", client=client)
    system = client.messages.calls[0]["system"].lower()
    assert "never suggest what to answer" in system
    assert "more likely to succeed" in system  # named in order to forbid it
