from pathlib import Path

from casesupport.criteria import load_criteria
from casesupport.models import CaseFile, Document
from casesupport.organizer import build_worksheet
from casesupport.provenance import UNKNOWN, Sourced

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


def test_verified_fact_appears_with_its_citation():
    fact = Sourced(
        "2019-03-03", "passport-stamp", 1, "Admitted at San Ysidro, California on 3 March 2019"
    ).verified_against(ENTRY_DOC.text)
    worksheet = build_worksheet(_case({"date_of_entry": fact}), load_criteria(FIXTURE))

    row = next(r for r in worksheet.rows if r.element.element_id == "date_of_entry")
    assert row.addressed
    assert "passport-stamp p.1 (verified)" in row.render()
    assert "2019-03-03" in row.render()


def test_missing_element_is_flagged_not_filled_in():
    worksheet = build_worksheet(
        _case({"date_of_entry": UNKNOWN, "filing_date": UNKNOWN}), load_criteria(FIXTURE)
    )
    assert set(worksheet.unaddressed_elements) == {"date_of_entry", "filing_date"}
    assert "NOT ADDRESSED" in worksheet.render()
    assert "Receipt notice" in worksheet.render()  # the evidence hint is shown


def test_unverified_extraction_is_discarded_and_disclosed():
    unverified = Sourced("2017-01-01", "passport-stamp", 1, "a quote that is not in the document")
    worksheet = build_worksheet(_case({"date_of_entry": unverified}), load_criteria(FIXTURE))

    row = next(r for r in worksheet.rows if r.element.element_id == "date_of_entry")
    assert not row.addressed
    assert "2017-01-01" not in row.render()
    assert "could not be verified" in row.render()


def test_unlinked_documents_are_surfaced():
    fact = Sourced(
        "2019-03-03", "passport-stamp", 1, "Admitted at San Ysidro, California on 3 March 2019"
    ).verified_against(ENTRY_DOC.text)
    worksheet = build_worksheet(_case({"date_of_entry": fact}), load_criteria(FIXTURE))
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
