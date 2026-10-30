# Immigration Case Support Tooling

Case support tooling for asylum and immigration benefit adjudication. AI handles
translation, transcription, and document organization. Officers apply the law and
own every decision. The software surfaces facts with citations to the documents
they came from; it does not evaluate people and it does not decide cases.

## Components

### Officer record organizer

Ingests the applicant's own submitted file. Extracts factual elements — dates of
entry and presence, filing dates, tax compliance where a statute makes it
relevant, and derivative family members listed on the application. Every
extracted fact is displayed next to the source document and page it came from.
Anything unreadable is marked `unknown`; it is never inferred or interpolated.
Submitted evidence is indexed against the statutory eligibility element it bears
on, as a worksheet for the officer to verify — not as a finding.

### Multilingual intake assistant

Explains each form field in the applicant's own language, accepts answers in that
language, and produces a clean English filing alongside a preserved
original-language record. Applicants should not lose a case because they do not
read English. No answer is scored or evaluated.

### Interview support

Interpretation and transcript generation for officer interviews, with the
original-language audio retained for appeal. Produces a record; assesses no one.

## Design constraints

These are hard rules, not defaults.

- **No government database access.** The system consumes only the applicant's
  submitted file and supporting evidence. It does not read from USCIS or any
  other government system of record.
- **No score, ranking, recommendation, or eligibility conclusion** is produced by
  the software.
- **Statutory criteria come from a reviewed, cited criteria file**, never from
  model memory. Benefit types have different and non-interchangeable eligibility
  standards; criteria for one must not leak into another.
- **Original-language source material is retained** for every derived artifact,
  for appeal and audit.
- **Every AI-derived field is attributed to its source** and marked unverified
  until an officer confirms it.

## Out of scope

The following are out of scope and will not be built for now:

- an AI score of someone's kindness, values, or whether they'd be "beneficial to
  the United States"
- medical condition as an evaluation input
- profiling of friends or family members who aren't themselves applicants
- an automated accept/adjudicate verdict

The main reason is engineering, not squeamishness. A robust system was asked for —
and there is no validated instrument for measuring a stranger's character from
text, in any language. An LLM asked to produce that number will produce a
confident-looking one that mostly reflects how fluent, coached, and culturally
legible the applicant is. That is the least robust thing that could ship, it is
the kind of system that gets enjoined on due-process and disability-discrimination
grounds, and litigation plus re-adjudication costs DHS far more than the officer
hours it saves. Medical condition and associates' data are what turn a bad tool
into an unlawful one.

## How provenance works

Every fact the software reports is a `Sourced` value carrying the document,
page, and verbatim quote it came from, plus a `verified` flag. The model is
asked for one factual element at a time and required to return the quote it
read the value from; the code then checks that quote against that page of that
document. A quote that does not appear there collapses to `UNKNOWN`, and the
officer is told the element is unaddressed rather than shown a value the record
never stated.

This is deliberately stricter than trusting the model's own citations. The
API's document-citation feature cannot be combined with structured JSON output
(the pairing returns a 400), and the local check is the better of the two
anyway: a fabricated quote fails a deterministic string comparison. `UNKNOWN`
is a distinct value from "absent" and from a default, and it is never filled
in.

The exclusions in *Out of scope* are partly machine-checked. `guardrails.py`
rejects excluded inputs (medical, associates) and conclusion-shaped outputs
(score, verdict, eligibility) anywhere in a record, schema, or criteria file,
and the test suite fails if that boundary is crossed.

## Repository layout

    src/casesupport/
      provenance.py   Sourced values, UNKNOWN, quote verification
      guardrails.py   enforced exclusions (inputs and output surface)
      models.py       Document, CaseFile, DerivativeFamilyMember
      criteria.py     loads human-reviewed criteria files; refuses unreviewed
      extraction.py   Claude-backed element reading, then local verification
      intake.py       multilingual field explanation and answer translation
      organizer.py    the officer's evidence worksheet
    criteria/         criteria file template (rejected by design until reviewed)
    examples/         runnable end-to-end demo, no API key needed
    tests/

## Running it

    python3 -m venv .venv          # Python 3.11 or newer
    .venv/bin/pip install -e ".[dev]"
    .venv/bin/python -m pytest     # no network, no API key
    .venv/bin/python examples/demo_worksheet.py

The demo uses a scripted fake client, so the whole path is inspectable offline.
One of its two model readings cites a quote that is not in the document; the
output shows that reading being discarded. Live extraction needs
`ANTHROPIC_API_KEY` or an `ant auth login` profile.

Model: `claude-opus-5`, with adaptive thinking. Extraction checks for a
`refusal` stop reason and treats it as `UNKNOWN` rather than crashing.

## Status

Pre-implementation on the officer-facing API and the interview component.
Implemented: provenance and verification, guardrails, criteria loading,
single-element extraction, intake translation, and worksheet rendering.

Not built yet:

- **Interview support** — not started. Of the three components, only the record
  organizer and intake assistant have code.
- The HTTP surface and persistence.
- Document ingest from PDF. `Document` is currently constructed from
  already-extracted page text.
- No criteria file for a real benefit type exists, and none should be written
  without a human verifying every citation.

Known limitations in what *is* built, both of which affect what an officer
sees and are the next things to fix:

- **Conflicting evidence is not surfaced.** `extract_elements` keeps the first
  verified reading per element. If two documents state different values for the
  same element, only one reaches the worksheet and the officer never sees the
  discrepancy — which is exactly the signal an adjudicator needs. `facts` needs
  to become multi-valued per element; `ElementRow.facts` is already a tuple in
  anticipation.
- **A failed verification is logged, not displayed.** When extraction proposes
  a value whose quote does not check out, the element shows as NOT ADDRESSED.
  The officer cannot currently distinguish "nothing in the record addresses
  this" from "a value was proposed and rejected", which are different
  situations. `organizer.ElementRow.unverified_note` renders this correctly but
  nothing in the live pipeline populates it.

## License

[0BSD](LICENSE) — use, copy, modify, and distribute for any purpose, with no
conditions and no attribution requirement.
