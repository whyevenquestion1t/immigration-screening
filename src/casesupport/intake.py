"""Multilingual intake assistant.

Helps an applicant understand and answer their own form in their own language,
then hands the officer an English filing with the original-language answers
preserved alongside it.

Two jobs, both language work:

  explain_field  -- say what a form field is asking, in the applicant's
                    language, plainly. Explains the question; never suggests an
                    answer, and never hints at which answer helps a case.
  render_answer  -- translate the applicant's own answer into English for the
                    filing, keeping the original verbatim.

Nothing here evaluates an answer. An intake tool that nudged answers toward
what adjudicators reward would be coaching, and would corrupt the record it
exists to produce.
"""

from __future__ import annotations

from dataclasses import dataclass

import anthropic
from pydantic import BaseModel, Field

MODEL = "claude-opus-5"

EXPLAIN_SYSTEM = """\
You explain what a government form field is asking, for someone filling in
their own application in a language they are more comfortable in.

- Explain the question in the target language, in plain words, at roughly a
  6th-grade reading level. Short sentences.
- Say what kind of answer the field wants (a date, a place, a yes or no, a
  narrative) and note the format if the form requires one.
- Never suggest what to answer. Never say which answer is better, stronger, or
  more likely to succeed. If the applicant would need legal advice to answer,
  say that this is a question for a lawyer or an accredited representative.
- If you are unsure what the field means, say so plainly instead of guessing.
"""

TRANSLATE_SYSTEM = """\
You translate an applicant's own answer on an immigration form into English for
the official filing.

- Translate faithfully and completely. Keep the applicant's meaning, register,
  and hedging. Do not smooth, strengthen, summarize, or make an answer sound
  more credible or more sympathetic.
- Keep names, places, dates, and numbers exactly as given; transliterate names
  rather than anglicizing them.
- If a passage is ambiguous or you cannot translate it confidently, translate it
  as literally as you can and flag it in `translator_notes` for human review.
- Add nothing the applicant did not say.
"""


class FieldExplanation(BaseModel):
    explanation: str = Field(description="The field explained in the target language.")
    answer_type: str = Field(description="What kind of answer the field wants.")
    needs_legal_advice: bool = Field(
        default=False,
        description="True if answering well requires a lawyer, not a translator.",
    )


class TranslatedAnswer(BaseModel):
    english: str = Field(description="Faithful English translation for the filing.")
    translator_notes: str = Field(
        default="", description="Ambiguities a human reviewer should check."
    )


@dataclass(frozen=True)
class IntakeAnswer:
    """One answered field, in both languages. Both go in the record."""

    field_id: str
    original_language: str
    original_text: str
    english_text: str
    translator_notes: str = ""


def explain_field(
    field_label: str,
    field_help: str,
    target_language: str,
    *,
    client: anthropic.Anthropic | None = None,
) -> FieldExplanation:
    client = client or anthropic.Anthropic()
    response = client.messages.parse(
        model=MODEL,
        max_tokens=16000,
        system=EXPLAIN_SYSTEM,
        thinking={"type": "adaptive"},
        messages=[
            {
                "role": "user",
                "content": (
                    f"Target language: {target_language}\n"
                    f"Field label: {field_label}\n"
                    f"Official instructions for the field: {field_help}"
                ),
            }
        ],
        output_format=FieldExplanation,
    )
    return response.parsed_output


def render_answer(
    field_id: str,
    answer_text: str,
    source_language: str,
    *,
    client: anthropic.Anthropic | None = None,
) -> IntakeAnswer:
    """Translate one answer, keeping the original verbatim in the record."""
    client = client or anthropic.Anthropic()
    response = client.messages.parse(
        model=MODEL,
        max_tokens=16000,
        system=TRANSLATE_SYSTEM,
        thinking={"type": "adaptive"},
        messages=[
            {
                "role": "user",
                "content": (
                    f"Source language: {source_language}\n"
                    f"Form field: {field_id}\n"
                    f"Applicant's answer:\n{answer_text}"
                ),
            }
        ],
        output_format=TranslatedAnswer,
    )
    parsed = response.parsed_output
    return IntakeAnswer(
        field_id=field_id,
        original_language=source_language,
        original_text=answer_text,
        english_text=parsed.english,
        translator_notes=parsed.translator_notes,
    )
