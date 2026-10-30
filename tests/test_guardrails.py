import pytest

from casesupport.guardrails import (
    ForbiddenField,
    check_inputs,
    check_output_surface,
)


def test_medical_condition_rejected():
    with pytest.raises(ForbiddenField, match="medical_condition"):
        check_inputs({"applicant": {"medical_condition": "none"}})


def test_associate_profiling_rejected():
    with pytest.raises(ForbiddenField):
        check_inputs({"known_associates": ["someone"]})
    with pytest.raises(ForbiddenField):
        check_inputs({"social_graph": {}})


def test_character_scoring_rejected_as_input_or_output():
    with pytest.raises(ForbiddenField):
        check_inputs({"values_score": 0.8})
    with pytest.raises(ForbiddenField):
        check_output_surface(["kindness"])
    with pytest.raises(ForbiddenField):
        check_output_surface(["benefit_to_country"])


def test_automated_verdict_rejected():
    for name in ("recommendation", "verdict", "decision", "eligible"):
        with pytest.raises(ForbiddenField):
            check_output_surface([name])


def test_nested_violations_are_found_with_a_path():
    with pytest.raises(ForbiddenField, match=r"case\.applicant\.diagnosis|diagnosis"):
        check_inputs({"case": {"applicant": {"diagnosis": "x"}}})

    with pytest.raises(ForbiddenField):
        check_inputs({"documents": [{"ok": 1}, {"risk_score": 2}]})


def test_legitimate_fields_pass():
    check_inputs(
        {
            "case_id": "A-1",
            "date_of_entry": "2019-03-03",
            "filing_date": "2019-08-01",
            "tax_filing_compliance": ["2019", "2020"],
            "derivative_family_members": [{"relationship": "spouse", "name": "X"}],
            "primary_language": "ps",
        }
    )
    check_output_surface(["date_of_entry", "filing_date", "continuous_presence_duration"])


def test_substring_collisions_are_not_false_positives():
    # Matching is whole-word, not substring: "contact_sheet_page" is not the
    # "contacts" field, and "scoreboard" is not "score". The check is
    # deliberately blunt in the other direction -- a field named
    # "decision_notice_document" is rejected even though it names a document,
    # because a false positive here costs a rename and a false negative does
    # not cost a rename.
    check_inputs({"contact_sheet_page": 2})
    check_output_surface(["applicant_declaration", "scoreboard_url_unused"])
