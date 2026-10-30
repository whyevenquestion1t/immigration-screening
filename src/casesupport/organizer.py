"""Officer record organizer: an evidence worksheet, not a finding.

Builds, for one case and one reviewed criteria set:

  * per element -- the verified facts in the record that bear on it, each with
    the document and page it came from, and the statutory citation the officer
    is working from;
  * which elements nothing in the record addresses;
  * which submitted documents are not yet linked to any element, so a relevant
    exhibit cannot be quietly lost.

What it deliberately does not do is say whether an element is satisfied. A
present document is not a met requirement, and the software has no standing to
decide the difference.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from casesupport.criteria import CriteriaSet, Element
from casesupport.guardrails import check_output_surface
from casesupport.models import CaseFile
from casesupport.provenance import Sourced, Unknown


@dataclass(frozen=True)
class ElementRow:
    """One element of the worksheet, as the officer sees it."""

    element: Element
    facts: tuple[Sourced[Any], ...]
    addressed: bool
    unverified_note: str | None = None

    def render(self) -> str:
        head = f"[{self.element.element_id}] {self.element.description}"
        cite = f"    criteria: {self.element.citation} <{self.element.source_url}>"
        if not self.addressed:
            hint = (
                f" Expected evidence: {self.element.evidence_hint}"
                if self.element.evidence_hint
                else ""
            )
            body = f"    NOT ADDRESSED by the submitted record.{hint}"
            if self.unverified_note:
                body += f"\n    note: {self.unverified_note}"
        else:
            body = "\n".join(
                f"    {fact.value}  <- {fact.citation()}"
                + (f"\n        note: {fact.note}" if fact.note else "")
                for fact in self.facts
            )
        return "\n".join([head, cite, body])


@dataclass(frozen=True)
class Worksheet:
    case_id: str
    benefit_type: str
    rows: tuple[ElementRow, ...]
    unaddressed_elements: tuple[str, ...]
    unlinked_documents: tuple[str, ...]
    criteria_reviewed: bool

    def render(self) -> str:
        banner = [
            f"Case {self.case_id} -- {self.benefit_type}",
            "Evidence worksheet. Facts below are extracted from the applicant's",
            "submitted file and attributed to their source. This worksheet makes",
            "no eligibility finding and no recommendation.",
        ]
        if not self.criteria_reviewed:
            banner.append(
                "WARNING: criteria set is not attested as human-reviewed. "
                "Not for use on a live case."
            )
        parts = ["\n".join(banner), ""]
        parts.extend(row.render() for row in self.rows)
        if self.unaddressed_elements:
            parts.append(
                "\nElements no submitted document addresses:\n"
                + "\n".join(f"  - {e}" for e in self.unaddressed_elements)
            )
        if self.unlinked_documents:
            parts.append(
                "\nSubmitted documents not linked to any element (review -- an\n"
                "exhibit the applicant filed may bear on something):\n"
                + "\n".join(f"  - {d}" for d in self.unlinked_documents)
            )
        return "\n\n".join(parts)


def build_worksheet(case: CaseFile, criteria: CriteriaSet) -> Worksheet:
    """Assemble the worksheet. Pure function over the record -- no model call."""
    check_output_surface(criteria.element_ids())

    linked_documents: set[str] = set()
    rows: list[ElementRow] = []
    unaddressed: list[str] = []

    for element in criteria.elements:
        fact = case.facts.get(element.element_id)
        verified: tuple[Sourced[Any], ...] = ()
        note = None

        if isinstance(fact, Sourced):
            if fact.verified:
                verified = (fact,)
                linked_documents.add(fact.document_id)
            else:
                # An unverified extraction is not evidence. Surface that a
                # value was proposed and rejected, rather than hiding it.
                note = (
                    f"an extracted value for this element could not be verified "
                    f"against {fact.document_id} and was discarded"
                )

        addressed = bool(verified)
        if not addressed:
            unaddressed.append(element.element_id)
        rows.append(
            ElementRow(
                element=element,
                facts=verified,
                addressed=addressed,
                unverified_note=note,
            )
        )

    unlinked = tuple(
        sorted(d.document_id for d in case.documents if d.document_id not in linked_documents)
    )
    return Worksheet(
        case_id=case.case_id,
        benefit_type=criteria.benefit_type,
        rows=tuple(rows),
        unaddressed_elements=tuple(unaddressed),
        unlinked_documents=unlinked,
        criteria_reviewed=criteria.reviewed,
    )
