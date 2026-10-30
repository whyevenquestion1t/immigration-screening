"""Provenance: a value cannot exist in this system without a verified source.

The central invariant. Every fact the software reports about an applicant is a
`Sourced` value carrying the document, page, and verbatim quote it came from,
and a `verified` flag that is only set once the quote has been confirmed to
appear in that document's text. A model-asserted quote that does not appear in
the source collapses to `UNKNOWN` rather than being reported.

This is deliberately stricter than trusting the model's own citations: a
hallucinated page reference fails a deterministic string comparison.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, replace
from typing import Generic, TypeVar

T = TypeVar("T")


class Unknown:
    """A fact that could not be read from the record.

    Distinct from `None`, which would read as "absent", and from a default
    value, which would read as fact. Unknown means: a human must look.
    """

    _instance: "Unknown | None" = None

    def __new__(cls) -> "Unknown":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __bool__(self) -> bool:
        return False

    def __repr__(self) -> str:
        return "UNKNOWN"


UNKNOWN = Unknown()


def normalize(text: str) -> str:
    """Collapse the differences that survive OCR and PDF text extraction.

    Unicode NFKC (ligatures, full-width forms), unified dash and quote
    characters, collapsed whitespace, casefolded. Does not strip punctuation --
    a quote that differs in punctuation is a different quote.
    """
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("­", "")  # soft hyphen, common in PDF extraction
    text = re.sub(r"[‐-―−]", "-", text)
    text = re.sub(r"[‘’‛′]", "'", text)
    text = re.sub(r"[“”‟″]", '"', text)
    text = re.sub(r"\s+", " ", text)
    return text.strip().casefold()


def quote_matches(document_text: str, quote: str, *, min_length: int = 8) -> bool:
    """True when `quote` appears verbatim in `document_text`, modulo normalization.

    Quotes shorter than `min_length` characters are rejected: a two-word quote
    matches too much of any document to be evidence of anything.
    """
    if not quote or not document_text:
        return False
    normalized_quote = normalize(quote)
    if len(normalized_quote) < min_length:
        return False
    return normalized_quote in normalize(document_text)


@dataclass(frozen=True)
class Sourced(Generic[T]):
    """A value together with where it came from.

    Construct unverified, then call `verified_against` with the source text.
    Nothing in this system should read `.value` without checking `.verified`;
    use `value_or_unknown()` to make that impossible to forget.
    """

    value: T
    document_id: str
    page: int | None
    quote: str
    verified: bool = False
    note: str | None = None

    def verified_against(self, document_text: str) -> "Sourced[T] | Unknown":
        """Confirm the quote against the source, or collapse to UNKNOWN.

        Returning UNKNOWN rather than an unverified value is the point: an
        unverifiable extraction must not be able to flow onward by accident.
        """
        if quote_matches(document_text, self.quote):
            return replace(self, verified=True)
        return UNKNOWN

    def value_or_unknown(self) -> T | Unknown:
        return self.value if self.verified else UNKNOWN

    def citation(self) -> str:
        """Human-readable attribution for display next to the value."""
        where = f"{self.document_id}"
        if self.page is not None:
            where += f" p.{self.page}"
        status = "verified" if self.verified else "UNVERIFIED"
        return f"{where} ({status})"
