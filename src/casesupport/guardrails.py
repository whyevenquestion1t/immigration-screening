"""Enforced exclusions.

The README states what this system does not do. This module makes a subset of
that machine-checkable, so the boundary fails a test run rather than surviving
to a design review.

Two kinds of exclusion:

  FORBIDDEN_FIELDS  -- data that must never become an input. Medical condition
                       and non-applicant associates are the disability-
                       discrimination and third-party-data problems; these do
                       not get safer with a better model.

  FORBIDDEN_OUTPUTS -- shapes of conclusion the software must not produce. The
                       officer decides; we show them the record.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

FORBIDDEN_FIELDS: frozenset[str] = frozenset(
    {
        "medical_condition",
        "diagnosis",
        "disability",
        "mental_health",
        "hiv_status",
        "pregnancy",
        "medications",
        "friends",
        "associates",
        "known_associates",
        "social_graph",
        "contacts",
        "religion",
        "political_affiliation",
        "sexual_orientation",
        "ethnicity",
    }
)

FORBIDDEN_OUTPUTS: frozenset[str] = frozenset(
    {
        "score",
        "risk_score",
        "values_score",
        "kindness",
        "character_score",
        "moral_character_score",
        "trustworthiness",
        "assimilation_score",
        "benefit_to_country",
        "recommendation",
        "verdict",
        "decision",
        "approve",
        "deny",
        "adjudicate",
        "eligible",
        "ineligible",
        "ranking",
        "percentile",
        "confidence_of_eligibility",
    }
)

_WORD = re.compile(r"[a-z0-9]+")


class ForbiddenField(ValueError):
    """Raised when excluded data or an excluded conclusion enters the system."""


def _tokens(name: str) -> set[str]:
    return set(_WORD.findall(name.lower()))


def _violations(names: Iterable[str], forbidden: frozenset[str]) -> list[str]:
    found = []
    for name in names:
        lowered = name.lower()
        tokens = _tokens(lowered)
        for term in forbidden:
            term_tokens = _tokens(term)
            # Exact key match, or every word of a multi-word term present.
            if lowered == term or (len(term_tokens) > 1 and term_tokens <= tokens):
                found.append(f"{name} (matches excluded term '{term}')")
                break
            # Single-word terms match as a whole word, not a substring, so
            # "contacts" is caught but "contact_sheet_page" is not.
            if len(term_tokens) == 1 and term_tokens <= tokens:
                found.append(f"{name} (matches excluded term '{term}')")
                break
    return found


def check_inputs(payload: Any, *, path: str = "") -> None:
    """Recursively reject excluded data anywhere in a record or schema.

    Call on anything crossing into the system: parsed model output, an API
    request body, a criteria file, an extraction schema.
    """
    if isinstance(payload, dict):
        bad = _violations((str(k) for k in payload), FORBIDDEN_FIELDS | FORBIDDEN_OUTPUTS)
        if bad:
            where = path or "<root>"
            raise ForbiddenField(
                f"excluded field(s) at {where}: {', '.join(bad)}. "
                "See README 'Out of scope' and guardrails.py."
            )
        for key, value in payload.items():
            check_inputs(value, path=f"{path}.{key}" if path else str(key))
    elif isinstance(payload, (list, tuple)):
        for index, value in enumerate(payload):
            check_inputs(value, path=f"{path}[{index}]")


def check_output_surface(names: Iterable[str]) -> None:
    """Reject conclusion-shaped names on anything the system reports outward."""
    bad = _violations(names, FORBIDDEN_OUTPUTS)
    if bad:
        raise ForbiddenField(
            f"this system does not produce conclusions: {', '.join(bad)}. "
            "The officer decides; the software shows the record."
        )
