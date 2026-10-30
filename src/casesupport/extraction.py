"""Extraction: ask Claude for a factual element, then verify its citation.

The model is used for reading comprehension across languages -- which is what it
is actually good at -- and for nothing else. It is asked for a single factual
element at a time, and required to return the verbatim quote and page it read
the value from. We then check that quote against the document ourselves
(`provenance.quote_matches`). An unverifiable answer becomes UNKNOWN.

Document citations in the API cannot be combined with structured JSON output
(the pairing returns a 400), which is why provenance is carried in the schema
and verified locally. The local check is the stronger of the two anyway: it
fails a fabricated quote deterministically.
"""

from __future__ import annotations

import logging
from typing import Any

import anthropic
from pydantic import BaseModel, Field

from casesupport.criteria import Element
from casesupport.guardrails import check_inputs
from casesupport.models import Document
from casesupport.provenance import UNKNOWN, Sourced, Unknown

logger = logging.getLogger(__name__)

MODEL = "claude-opus-5"

SYSTEM = """\
You read immigration case documents and report single factual elements.

Rules:
- Report only what the document states. Never infer, estimate, or fill a gap.
- If the document does not state the element, set found=false. "Not stated" is
  a correct and useful answer; a guess is not.
- `quote` must be copied verbatim from the document, long enough to locate
  (at least a full clause). It is checked against the source; a quote that does
  not appear there causes your answer to be discarded.
- `page` is the 1-indexed page the quote appears on.
- Documents may be in any language. Quote in the document's original language;
  give `value` in English.
- Do not comment on the person. You are not assessing anyone's character,
  credibility, or worthiness, and no question here asks you to.
"""


class ElementReading(BaseModel):
    """What the model returns for one element. Provenance is mandatory."""

    found: bool = Field(description="Does the document state this element?")
    value: str = Field(default="", description="The element's value, in English.")
    quote: str = Field(default="", description="Verbatim quote from the document.")
    page: int | None = Field(default=None, description="1-indexed page of the quote.")
    reasoning: str = Field(
        default="", description="One sentence on where in the document this came from."
    )


def extract_element(
    element: Element,
    document: Document,
    *,
    client: anthropic.Anthropic | None = None,
) -> Sourced[str] | Unknown:
    """Read one element from one document, or return UNKNOWN.

    `client` is injectable so tests and offline runs never reach the network.
    """
    client = client or anthropic.Anthropic()

    numbered = "\n\n".join(
        f"--- page {i} ---\n{page}" for i, page in enumerate(document.pages, start=1)
    )
    question = (
        f"Element to find: {element.description}\n"
        f"(internal id: {element.element_id})\n\n"
        f"Document: {document.title}\n\n{numbered}"
    )

    response = client.messages.parse(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": question}],
        output_format=ElementReading,
    )

    # Safety classifiers can decline a request: HTTP 200 with stop_reason
    # "refusal" and no usable content. Check before reading the parse.
    if getattr(response, "stop_reason", None) == "refusal":
        details = getattr(response, "stop_details", None)
        logger.warning(
            "extraction refused for %s/%s: %s",
            document.document_id,
            element.element_id,
            getattr(details, "category", None),
        )
        return UNKNOWN

    reading = response.parsed_output
    if reading is None or not reading.found:
        return UNKNOWN

    check_inputs(reading.model_dump())

    candidate: Sourced[str] = Sourced(
        value=reading.value,
        document_id=document.document_id,
        page=reading.page,
        quote=reading.quote,
        note=reading.reasoning or None,
    )

    # Verify against the cited page when one was given, else the whole document.
    # A quote that is real but on a different page is still a bad citation: the
    # officer is being told where to look.
    if reading.page is not None:
        try:
            scope = document.page_text(reading.page)
        except IndexError:
            logger.warning(
                "%s cited page %s, which does not exist", document.document_id, reading.page
            )
            return UNKNOWN
    else:
        scope = document.text

    result = candidate.verified_against(scope)
    if isinstance(result, Unknown):
        logger.warning(
            "discarded unverifiable quote for %s/%s",
            document.document_id,
            element.element_id,
        )
    return result


def extract_elements(
    elements: list[Element],
    documents: list[Document],
    *,
    client: anthropic.Anthropic | None = None,
) -> dict[str, Sourced[Any] | Unknown]:
    """Read every element across every document; first verified hit wins.

    Elements no document answers are recorded as UNKNOWN rather than omitted,
    so the worksheet can show the officer what is missing.
    """
    client = client or anthropic.Anthropic()
    facts: dict[str, Sourced[Any] | Unknown] = {}
    for element in elements:
        facts[element.element_id] = UNKNOWN
        for document in documents:
            result = extract_element(element, document, client=client)
            if isinstance(result, Sourced):
                facts[element.element_id] = result
                break
    return facts
