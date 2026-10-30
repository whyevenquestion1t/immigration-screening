"""Case support tooling for immigration benefit adjudication.

Three components: a record organizer, a multilingual intake assistant, and
interview transcription. The package surfaces facts attributed to their source
documents and leaves every legal judgment to a human officer.

It does not compute scores, rankings, recommendations, or eligibility
conclusions. See `guardrails.py` for the enforced exclusions.
"""

from casesupport.provenance import Sourced, Unknown, UNKNOWN, quote_matches

__all__ = ["Sourced", "Unknown", "UNKNOWN", "quote_matches"]
