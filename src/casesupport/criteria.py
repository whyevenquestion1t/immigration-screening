"""Statutory criteria, loaded only from a human-reviewed file.

The controlling eligibility criteria for a benefit type are law, and they are
not the same across benefit types. Nothing in this package may supply them from
a model's memory or from an LLM call -- an invented or cross-applied citation in
an adjudication tool is worse than no tool.

So a criteria file must carry, per element, a `citation` and a `source_url`, and
per file a `reviewed_by` and `reviewed_on`. A file missing any of those loads
only with `allow_unreviewed=True`, which is for tests and never for a real case.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from casesupport.guardrails import check_inputs


class UnreviewedCriteria(RuntimeError):
    """Raised when criteria are not attested as human-reviewed."""


@dataclass(frozen=True)
class Element:
    """One factual element an officer must find in the record.

    `prompt` describes the factual question only (a date, a duration, whether a
    document is present). An element that asks for a judgment about the person
    does not belong in a criteria file.
    """

    element_id: str
    description: str
    citation: str
    source_url: str
    evidence_hint: str = ""


@dataclass(frozen=True)
class CriteriaSet:
    benefit_type: str
    reviewed_by: str
    reviewed_on: date
    elements: tuple[Element, ...]
    reviewed: bool = True

    def element(self, element_id: str) -> Element:
        for el in self.elements:
            if el.element_id == element_id:
                return el
        raise KeyError(f"no element {element_id!r} in {self.benefit_type} criteria")

    def element_ids(self) -> list[str]:
        return [el.element_id for el in self.elements]


def load_criteria(path: str | Path, *, allow_unreviewed: bool = False) -> CriteriaSet:
    raw: dict[str, Any] = yaml.safe_load(Path(path).read_text())
    check_inputs(raw)

    missing_attestation = [k for k in ("reviewed_by", "reviewed_on") if not raw.get(k)]
    incomplete = [
        el.get("element_id", "<unnamed>")
        for el in raw.get("elements") or []
        if not el.get("citation") or not el.get("source_url")
    ]

    if (missing_attestation or incomplete) and not allow_unreviewed:
        problems = []
        if missing_attestation:
            problems.append(f"file is missing {', '.join(missing_attestation)}")
        if incomplete:
            problems.append(
                f"elements missing citation/source_url: {', '.join(incomplete)}"
            )
        raise UnreviewedCriteria(
            f"{path}: {'; '.join(problems)}. A human with the statute in front of "
            "them must fill these in. Do not generate them."
        )

    reviewed_on = raw.get("reviewed_on")
    return CriteriaSet(
        benefit_type=raw["benefit_type"],
        reviewed_by=raw.get("reviewed_by") or "",
        reviewed_on=reviewed_on if isinstance(reviewed_on, date) else date.min,
        elements=tuple(
            Element(
                element_id=el["element_id"],
                description=el["description"],
                citation=el.get("citation") or "",
                source_url=el.get("source_url") or "",
                evidence_hint=el.get("evidence_hint", ""),
            )
            for el in raw.get("elements") or []
        ),
        reviewed=not (missing_attestation or incomplete),
    )
