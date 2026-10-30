"""Record types.

Everything here describes the applicant's own submitted file. There is no type
for a non-applicant third party, and no field for a conclusion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from casesupport.guardrails import check_inputs
from casesupport.provenance import Sourced, Unknown


@dataclass(frozen=True)
class Document:
    """One submitted document, with its extracted text.

    `pages` is 1-indexed text per page so a quote can be attributed to a page.
    `text` is the concatenation used for quote verification.
    """

    document_id: str
    title: str
    pages: tuple[str, ...]
    language: str | None = None
    received_on: date | None = None

    @property
    def text(self) -> str:
        return "\n".join(self.pages)

    def page_text(self, page: int) -> str:
        if not 1 <= page <= len(self.pages):
            raise IndexError(f"{self.document_id} has no page {page}")
        return self.pages[page - 1]


@dataclass(frozen=True)
class DerivativeFamilyMember:
    """A family member listed on the application as a derivative.

    In scope only because the applicant named them on their own form and their
    status rides on this application. This is not a record of relatives in
    general, and nothing here supports looking anyone up.
    """

    relationship: str
    name: Sourced[str] | Unknown
    date_of_birth: Sourced[date] | Unknown


@dataclass(frozen=True)
class CaseFile:
    """The applicant's submitted file, as received.

    `facts` holds extracted factual elements keyed by element id, each one
    Sourced or UNKNOWN. No derived score, no summary judgment.
    """

    case_id: str
    documents: tuple[Document, ...]
    facts: dict[str, Sourced[Any] | Unknown] = field(default_factory=dict)
    derivatives: tuple[DerivativeFamilyMember, ...] = ()
    primary_language: str | None = None

    def __post_init__(self) -> None:
        check_inputs(self.facts)

    def document(self, document_id: str) -> Document:
        for doc in self.documents:
            if doc.document_id == document_id:
                return doc
        raise KeyError(f"no document {document_id!r} in case {self.case_id}")

    def unknown_facts(self) -> list[str]:
        """Element ids the record did not answer -- the officer's to-do list."""
        return sorted(k for k, v in self.facts.items() if isinstance(v, Unknown))
