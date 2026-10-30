"""Officer record organizer: an evidence worksheet, not a finding.

Builds, for one case and one reviewed criteria set:

  * per element -- the verified facts in the record that bear on it, each with
    the document and page it came from, and the statutory citation the officer
    is working from;
  * which elements nothing in the record addresses;
  * which elements the record states more than one value for, flagged as a
    conflict for the officer to resolve rather than silently reduced to one;
  * which readings were discarded for failing quote verification, so a missing
    element and a rejected extraction do not look alike;
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
from casesupport.models import CaseFile, ElementFindings
from casesupport.provenance import Sourced


@dataclass(frozen=True)
class ElementRow:
    """One element of the worksheet, as the officer sees it."""

    element: Element
    facts: tuple[Sourced[Any], ...]
    addressed: bool
    conflicting: bool = False
    distinct_values: tuple[str, ...] = ()
    discarded: tuple[Sourced[Any], ...] = ()

    def _discarded_note(self) -> list[str]:
        """Disclose readings that failed verification, without their values.

        The officer is told an attempt was made and rejected, and where it
        claimed to come from. The value itself is withheld: it did not survive
        verification, so showing it would put an unsourced number in front of
        the person deciding the case.
        """
        if not self.discarded:
            return []
        where = ", ".join(sorted({d.document_id for d in self.discarded}))
        return [
            f"    [{len(self.discarded)} reading(s) discarded: a value was extracted "
            f"from {where} but its",
            "     quote could not be verified against the source. Value withheld; "
            "read the document.]",
        ]

    def render(self) -> str:
        lines = [
            f"[{self.element.element_id}] {self.element.description}",
            f"    criteria: {self.element.citation} <{self.element.source_url}>",
        ]
        if self.conflicting:
            lines.append(
                "    *** CONFLICT: the record states "
                f"{len(self.distinct_values)} different values for this element. "
                "Officer must resolve. ***"
            )
        if not self.addressed:
            hint = (
                f" Expected evidence: {self.element.evidence_hint}"
                if self.element.evidence_hint
                else ""
            )
            lines.append(f"    NOT ADDRESSED by the submitted record.{hint}")
        else:
            for fact in self.facts:
                lines.append(f"    {fact.value}  <- {fact.citation()}")
                if fact.note:
                    lines.append(f"        note: {fact.note}")
        lines.extend(self._discarded_note())
        return "\n".join(lines)


@dataclass(frozen=True)
class Worksheet:
    case_id: str
    benefit_type: str
    rows: tuple[ElementRow, ...]
    unaddressed_elements: tuple[str, ...]
    conflicting_elements: tuple[str, ...]
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
        if self.conflicting_elements:
            parts.append(
                "\nElements the record states more than one value for -- resolve\n"
                "before relying on any of them:\n"
                + "\n".join(f"  - {e}" for e in self.conflicting_elements)
            )
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
    conflicting: list[str] = []

    for element in criteria.elements:
        findings = case.facts.get(element.element_id) or ElementFindings()

        # Only verified readings are evidence. A document a rejected reading
        # claimed to come from still counts as linked -- the officer was sent
        # there, so it is not an unreviewed exhibit.
        for fact in findings.verified:
            linked_documents.add(fact.document_id)
        for discarded in findings.rejected:
            linked_documents.add(discarded.document_id)

        if not findings.addressed:
            unaddressed.append(element.element_id)
        if findings.conflicting:
            conflicting.append(element.element_id)

        rows.append(
            ElementRow(
                element=element,
                facts=findings.verified,
                addressed=findings.addressed,
                conflicting=findings.conflicting,
                distinct_values=tuple(findings.distinct_values()),
                discarded=findings.rejected,
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
        conflicting_elements=tuple(conflicting),
        unlinked_documents=unlinked,
        criteria_reviewed=criteria.reviewed,
    )
