"""Render a worksheet end-to-end with no API key and no network.

    python examples/demo_worksheet.py

Uses a fake extraction client so the full path -- documents in, model reading,
quote verification, worksheet out -- is visible and inspectable. One of the two
model readings below cites a quote that is not in the document; watch what
happens to it.
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
    pages=("Receipt notice. We received your application.",),
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

    client = FakeClient(
        # date_of_entry, read from the I-94: quote is real and on page 2.
        FakeResponse(
            ElementReading(
                found=True,
                value="2019-03-03",
                quote="Date of admission: 3 March 2019",
                page=2,
                reasoning="Stated in the admission field of the arrival record.",
            )
        ),
        # filing_date: the receipt notice does not actually state a date, and
        # this reading invents one with a quote that is not in the document.
        FakeResponse(
            ElementReading(
                found=True,
                value="2019-08-01",
                quote="Application filed on 1 August 2019",
                page=1,
                reasoning="Receipt notice.",
            )
        ),
    )

    documents = [I94, RECEIPT, LEASE]
    facts = extract_elements(list(criteria.elements), documents, client=client)
    case = CaseFile(case_id="A-000-000-000", documents=tuple(documents), facts=facts)

    print(build_worksheet(case, criteria).render())
    print("\n" + "-" * 70)
    print("Elements the record did not answer:", case.unknown_facts())
    print(
        "The filing_date reading above was discarded: its quote does not appear\n"
        "in the receipt notice. The officer is told the element is unaddressed\n"
        "rather than shown a date the document never stated."
    )


if __name__ == "__main__":
    main()
