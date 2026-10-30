# Criteria files

A criteria file lists the **factual elements** an officer must find in the
record for one benefit type, with the statutory citation each element comes
from.

These files are law. They are written and signed off by a person with the
statute in front of them. Do not generate one with an LLM, and do not copy
elements between benefit types — asylum, adjustment of status, and
naturalization have different and non-interchangeable standards, and a
cross-applied citation is a defect that reaches an applicant.

`load_criteria()` refuses any file that is missing `reviewed_by`, `reviewed_on`,
or a per-element `citation` and `source_url`. `example.unreviewed.yaml` is
intentionally incomplete and is rejected by design; it is a template, not a
usable criteria set.

An element states a factual question — a date, a duration, whether a document
is present. If an element asks for a judgment about the applicant as a person,
it does not belong in one of these files.
