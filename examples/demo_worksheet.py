"""Render a worksheet end-to-end with no API key and no network.

    python examples/demo_worksheet.py

Uses a fake extraction client so the full path -- documents in, model reading,
quote verification, worksheet out -- is visible and inspectable. The scripted
readings cover the three cases that matter: one verifies, one cites a quote
that is not in the document, and two disagree with each other.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from casesupport.criteria import load_criteria
from casesupport.extraction import ElementReading, extract_elements
from casesupport.models import CaseFile, Document
from casesupport.organizer import build_worksheet

I94 = Document(
    document_id="i94",
    title="Form I-94 arrival record",
    pages=(
        "U.S. Customs and Border Protection arrival record.",
        "Date of admission: 3 March 2019. Class of admission: B2.",
    ),
)
RECEIPT = Document(
    document_id="receipt-notice",
    title="Receipt notice",
    pages=("Receipt notice. We received your application on 1 August 2019.",),
)
LEASE = Document(
    document_id="lease",
    title="Residential lease",
    pages=("Lease term 1 June 2019 through 31 May 2024.",),
)


@dataclass
class FakeResponse:
    parsed_output: Any
    stop_reason: str = "end_turn"
    stop_details: Any = None


class FakeMessages:
    def __init__(self, readings):
        self._readings = list(readings)

    def parse(self, **_):
        return self._readings.pop(0) if self._readings else FakeResponse(
            ElementReading(found=False)
        )


class FakeClient:
    """Stands in for anthropic.Anthropic. Scripted, in call order."""

    def __init__(self, *readings):
        self.messages = FakeMessages(readings)


def main() -> None:
    criteria = load_criteria(Path(__file__).parent.parent / "tests" / "fixtures" / "reviewed.yaml")

    # Every element is read from every document, so the scripted responses are
    # in (element, document) order: date_of_entry x 3, then filing_date x 3.
    client = FakeClient(
        # date_of_entry from the I-94: quote is real and on page 2.
        FakeResponse(
            ElementReading(
                found=True,
                value="2019-03-03",
                quote="Date of admission: 3 March 2019",
                page=2,
                reasoning="Stated in the admission field of the arrival record.",
            )
        ),
        # date_of_entry from the receipt notice: not stated there.
        FakeResponse(ElementReading(found=False)),
        # date_of_entry from the lease: a different date, and the quote checks
        # out. Two documents now disagree -- the officer must see both.
        FakeResponse(
            ElementReading(
                found=True,
                value="2019-06-01",
                quote="Lease term 1 June 2019 through 31 May 2024",
                page=1,
                reasoning="Lease start date.",
            )
        ),
        # filing_date from the I-94: not stated.
        FakeResponse(ElementReading(found=False)),
        # filing_date from the receipt notice: right answer, but the quote is
        # paraphrased rather than copied -- so it fails verification.
        FakeResponse(
            ElementReading(
                found=True,
                value="2019-08-01",
                quote="Application filed on 1 August 2019",
                page=1,
                reasoning="Receipt notice.",
            )
        ),
        # filing_date from the lease: not stated.
        FakeResponse(ElementReading(found=False)),
    )

    documents = [I94, RECEIPT, LEASE]
    facts = extract_elements(list(criteria.elements), documents, client=client)
    case = CaseFile(case_id="A-000-000-000", documents=tuple(documents), facts=facts)

    print(build_worksheet(case, criteria).render())
    print("\n" + "-" * 70)
    print("Elements the record did not answer:  ", case.unknown_facts())
    print("Elements with conflicting evidence:  ", case.conflicting_facts())
    print(
        "\ndate_of_entry: two documents verify different dates. Both are shown\n"
        "with their own citation and the element is flagged CONFLICT. The\n"
        "software does not pick one.\n\n"
        "filing_date: the reading was right about the date but paraphrased the\n"
        "quote, so verification failed. The officer is told a reading was\n"
        "discarded and sent to the document -- not shown the unsourced value."
    )


if __name__ == "__main__":
    main()
