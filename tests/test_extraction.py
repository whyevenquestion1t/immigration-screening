"""Extraction tests. No network: a fake client returns canned model output.

The point of these tests is the verification step -- that a plausible-looking
answer with a fabricated quote cannot become a fact.
"""

from dataclasses import dataclass
from typing import Any

from casesupport.criteria import Element
from casesupport.guardrails import check_output_surface
from casesupport.extraction import ElementReading, extract_element, extract_elements
from casesupport.models import Document
from casesupport.models import ElementFindings
from casesupport.provenance import Sourced

DOC = Document(
    document_id="i94",
    title="Form I-94 arrival record",
    pages=(
        "U.S. Customs and Border Protection arrival record.",
        "Date of admission: 3 March 2019. Class of admission: B2.",
    ),
)

ELEMENT = Element(
    element_id="date_of_entry",
    description="Date the applicant last entered the United States.",
    citation="TEST-PLACEHOLDER",
    source_url="https://example.invalid",
)


@dataclass
class FakeResponse:
    parsed_output: Any
    stop_reason: str = "end_turn"
    stop_details: Any = None


class FakeMessages:
    def __init__(self, readings):
        self._readings = list(readings)
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return self._readings.pop(0)


class FakeClient:
    def __init__(self, *readings):
        self.messages = FakeMessages(readings)


def test_verified_reading_becomes_a_sourced_fact():
    client = FakeClient(
        FakeResponse(
            ElementReading(
                found=True,
                value="2019-03-03",
                quote="Date of admission: 3 March 2019",
                page=2,
                reasoning="Stated on the arrival record.",
            )
        )
    )
    result = extract_element(ELEMENT, DOC, client=client)
    assert result.verified is not None and result.rejected is None
    assert isinstance(result.verified, Sourced)
    assert result.verified.value == "2019-03-03" and result.verified.page == 2


def test_fabricated_quote_is_discarded():
    client = FakeClient(
        FakeResponse(
            ElementReading(
                found=True,
                value="2017-01-01",
                quote="Date of admission: 1 January 2017",
                page=2,
            )
        )
    )
    result = extract_element(ELEMENT, DOC, client=client)
    assert result.verified is None
    # Retained as a rejected reading so the worksheet can disclose the attempt.
    assert result.rejected is not None and result.rejected.value == "2017-01-01"


def test_real_quote_cited_to_the_wrong_page_is_discarded():
    # The quote exists in the document, but not on the page the officer is
    # being told to look at.
    client = FakeClient(
        FakeResponse(
            ElementReading(
                found=True, value="2019-03-03", quote="Date of admission: 3 March 2019", page=1
            )
        )
    )
    result = extract_element(ELEMENT, DOC, client=client)
    assert result.verified is None and result.rejected is not None


def test_nonexistent_page_is_discarded():
    client = FakeClient(
        FakeResponse(
            ElementReading(
                found=True, value="2019-03-03", quote="Date of admission: 3 March 2019", page=99
            )
        )
    )
    result = extract_element(ELEMENT, DOC, client=client)
    assert result.verified is None and result.rejected is not None


def test_not_found_yields_nothing_at_all():
    client = FakeClient(FakeResponse(ElementReading(found=False)))
    result = extract_element(ELEMENT, DOC, client=client)
    assert result.verified is None and result.rejected is None and not result.refused


def test_refusal_is_handled_not_crashed():
    client = FakeClient(FakeResponse(parsed_output=None, stop_reason="refusal"))
    result = extract_element(ELEMENT, DOC, client=client)
    assert result.refused is True and result.verified is None


def test_elements_never_silently_omitted():
    client = FakeClient(FakeResponse(ElementReading(found=False)))
    facts = extract_elements([ELEMENT], [DOC], client=client)
    assert facts == {"date_of_entry": ElementFindings()}
    assert not facts["date_of_entry"].addressed


OTHER_DOC = Document(
    document_id="lease",
    title="Residential lease",
    pages=("Tenant took occupancy on 1 January 2017.",),
)


def test_every_document_is_read_so_conflicts_survive():
    # Both documents answer the element, and they disagree. First-hit-wins
    # would hide that; the officer needs to see it.
    client = FakeClient(
        FakeResponse(
            ElementReading(
                found=True, value="2019-03-03", quote="Date of admission: 3 March 2019", page=2
            )
        ),
        FakeResponse(
            ElementReading(
                found=True,
                value="2017-01-01",
                quote="Tenant took occupancy on 1 January 2017",
                page=1,
            )
        ),
    )
    facts = extract_elements([ELEMENT], [DOC, OTHER_DOC], client=client)
    findings = facts["date_of_entry"]

    assert len(findings.verified) == 2
    assert findings.conflicting is True
    assert findings.distinct_values() == ["2017-01-01", "2019-03-03"]


def test_rejected_readings_are_collected_across_documents():
    client = FakeClient(
        FakeResponse(
            ElementReading(found=True, value="x", quote="a quote that is not present", page=2)
        ),
        FakeResponse(
            ElementReading(found=True, value="y", quote="also not in this document", page=1)
        ),
    )
    findings = extract_elements([ELEMENT], [DOC, OTHER_DOC], client=client)["date_of_entry"]
    assert findings.verified == ()
    assert len(findings.rejected) == 2
    assert not findings.addressed


def test_schema_offers_no_field_for_a_judgment_about_the_person():
    # A keyword scan of the prompt cannot tell "assess credibility" from "do
    # not assess credibility" -- the system prompt contains those words in
    # order to forbid them. The checkable property is the output schema: the
    # model is given nowhere to put an opinion about the applicant.
    assert set(ElementReading.model_fields) == {
        "found",
        "value",
        "quote",
        "page",
        "reasoning",
    }
    check_output_surface(ElementReading.model_fields)


def test_prompt_forbids_inference_and_names_the_right_model():
    client = FakeClient(FakeResponse(ElementReading(found=False)))
    extract_element(ELEMENT, DOC, client=client)
    sent = client.messages.calls[0]
    assert sent["model"] == "claude-opus-5"
    system = sent["system"].lower()
    assert "never infer" in system
    assert "not assessing anyone's character" in system
    # Every page is shown to the model, labelled, so a page citation is checkable.
    content = str(sent["messages"])
    assert "--- page 1 ---" in content and "--- page 2 ---" in content
