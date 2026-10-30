from pathlib import Path

from casesupport.criteria import load_criteria
from casesupport.models import CaseFile, Document, ElementFindings
from casesupport.organizer import build_worksheet
from casesupport.provenance import Sourced

FIXTURE = Path(__file__).parent / "fixtures" / "reviewed.yaml"

ENTRY_DOC = Document(
    document_id="passport-stamp",
    title="Passport entry stamp",
    pages=("Admitted at San Ysidro, California on 3 March 2019.",),
)
STRAY_DOC = Document(
    document_id="school-records",
    title="School enrollment records",
    pages=("Enrolled 2019-2024.",),
)


def _case(facts):
    return CaseFile(
        case_id="A-1",
        documents=(ENTRY_DOC, STRAY_DOC),
        facts=facts,
    )


def _verified(value, doc=ENTRY_DOC, quote="Admitted at San Ysidro, California on 3 March 2019"):
    fact = Sourced(value, doc.document_id, 1, quote).verified_against(doc.text)
    assert isinstance(fact, Sourced), "fixture quote must actually verify"
    return fact


def test_verified_fact_appears_with_its_citation():
    worksheet = build_worksheet(
        _case({"date_of_entry": ElementFindings(verified=(_verified("2019-03-03"),))}),
        load_criteria(FIXTURE),
    )

    row = next(r for r in worksheet.rows if r.element.element_id == "date_of_entry")
    assert row.addressed
    assert "passport-stamp p.1 (verified)" in row.render()
    assert "2019-03-03" in row.render()


def test_missing_element_is_flagged_not_filled_in():
    worksheet = build_worksheet(
        _case({"date_of_entry": ElementFindings(), "filing_date": ElementFindings()}),
        load_criteria(FIXTURE),
    )
    assert set(worksheet.unaddressed_elements) == {"date_of_entry", "filing_date"}
    assert "NOT ADDRESSED" in worksheet.render()
    assert "Receipt notice" in worksheet.render()  # the evidence hint is shown


def test_unverified_extraction_is_discarded_and_disclosed():
    rejected = Sourced("2017-01-01", "passport-stamp", 1, "a quote that is not in the document")
    worksheet = build_worksheet(
        _case({"date_of_entry": ElementFindings(rejected=(rejected,))}), load_criteria(FIXTURE)
    )

    row = next(r for r in worksheet.rows if r.element.element_id == "date_of_entry")
    rendered = row.render()
    assert not row.addressed
    # The officer learns an attempt failed, and does not see the bad value.
    assert "2017-01-01" not in rendered
    assert "discarded" in rendered
    assert "could not be verified" in rendered
    assert "passport-stamp" in rendered


def test_conflicting_values_are_flagged_not_reconciled():
    findings = ElementFindings(
        verified=(
            _verified("2019-03-03"),
            _verified("2017-01-01", doc=STRAY_DOC, quote="Enrolled 2019-2024"),
        )
    )
    worksheet = build_worksheet(_case({"date_of_entry": findings}), load_criteria(FIXTURE))
    rendered = worksheet.render()

    assert worksheet.conflicting_elements == ("date_of_entry",)
    assert "CONFLICT" in rendered
    assert "Officer must resolve" in rendered
    # Both values stay visible with their own citations; neither is dropped.
    assert "2019-03-03" in rendered and "2017-01-01" in rendered
    assert "passport-stamp" in rendered and "school-records" in rendered


def test_agreeing_documents_are_not_a_conflict():
    findings = ElementFindings(
        verified=(
            _verified("2019-03-03"),
            _verified("2019-03-03", doc=STRAY_DOC, quote="Enrolled 2019-2024"),
        )
    )
    worksheet = build_worksheet(_case({"date_of_entry": findings}), load_criteria(FIXTURE))
    assert worksheet.conflicting_elements == ()
    assert "CONFLICT" not in worksheet.render()


def test_unlinked_documents_are_surfaced():
    worksheet = build_worksheet(
        _case({"date_of_entry": ElementFindings(verified=(_verified("2019-03-03"),))}),
        load_criteria(FIXTURE),
    )
    assert worksheet.unlinked_documents == ("school-records",)


def test_worksheet_states_it_makes_no_finding():
    worksheet = build_worksheet(_case({}), load_criteria(FIXTURE))
    rendered = worksheet.render().lower()
    assert "no eligibility finding and no recommendation" in rendered
    for word in ("approved", "denied", "score", "recommend "):
        assert word not in rendered


def test_unreviewed_criteria_produce_a_loud_warning():
    template = Path(__file__).parent.parent / "criteria" / "example.unreviewed.yaml"
    worksheet = build_worksheet(_case({}), load_criteria(template, allow_unreviewed=True))
    assert "not attested as human-reviewed" in worksheet.render()
