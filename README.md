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

## Status

Pre-implementation. This repository establishes scope; no application code yet.

## License

[0BSD](LICENSE) — use, copy, modify, and distribute for any purpose, with no
conditions and no attribution requirement.
