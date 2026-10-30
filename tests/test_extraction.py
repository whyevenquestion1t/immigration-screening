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
from casesupport.provenance import UNKNOWN, Sourced

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
    assert isinstance(result, Sourced)
    assert result.verified and result.value == "2019-03-03" and result.page == 2


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
    assert extract_element(ELEMENT, DOC, client=client) is UNKNOWN


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
    assert extract_element(ELEMENT, DOC, client=client) is UNKNOWN


def test_nonexistent_page_is_discarded():
    client = FakeClient(
        FakeResponse(
            ElementReading(
                found=True, value="2019-03-03", quote="Date of admission: 3 March 2019", page=99
            )
        )
    )
    assert extract_element(ELEMENT, DOC, client=client) is UNKNOWN


def test_not_found_stays_unknown():
    client = FakeClient(FakeResponse(ElementReading(found=False)))
    assert extract_element(ELEMENT, DOC, client=client) is UNKNOWN


def test_refusal_is_handled_not_crashed():
    client = FakeClient(FakeResponse(parsed_output=None, stop_reason="refusal"))
    assert extract_element(ELEMENT, DOC, client=client) is UNKNOWN


def test_elements_never_silently_omitted():
    client = FakeClient(FakeResponse(ElementReading(found=False)))
    facts = extract_elements([ELEMENT], [DOC], client=client)
    assert facts == {"date_of_entry": UNKNOWN}


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
