from pathlib import Path

import pytest

from casesupport.criteria import UnreviewedCriteria, load_criteria

FIXTURE = Path(__file__).parent / "fixtures" / "reviewed.yaml"
TEMPLATE = Path(__file__).parent.parent / "criteria" / "example.unreviewed.yaml"


def test_reviewed_file_loads():
    criteria = load_criteria(FIXTURE)
    assert criteria.benefit_type == "TEST_BENEFIT"
    assert criteria.reviewed is True
    assert criteria.element_ids() == ["date_of_entry", "filing_date"]
    assert criteria.element("filing_date").source_url.startswith("https://")


def test_template_is_refused_because_it_is_unreviewed():
    # The shipped template has no reviewer attestation and no citations. It must
    # not be loadable for a real case.
    with pytest.raises(UnreviewedCriteria) as err:
        load_criteria(TEMPLATE)
    message = str(err.value)
    assert "reviewed_by" in message
    assert "citation" in message


def test_unreviewed_can_be_forced_but_is_flagged(tmp_path):
    forced = load_criteria(TEMPLATE, allow_unreviewed=True)
    assert forced.reviewed is False


def test_missing_citation_on_one_element_fails_the_whole_file(tmp_path):
    path = tmp_path / "partial.yaml"
    path.write_text(
        "benefit_type: T\n"
        "reviewed_by: Someone\n"
        "reviewed_on: 2026-01-01\n"
        "elements:\n"
        "  - element_id: good\n"
        "    description: d\n"
        "    citation: C\n"
        "    source_url: https://example.invalid\n"
        "  - element_id: bad\n"
        "    description: d\n"
    )
    with pytest.raises(UnreviewedCriteria, match="bad"):
        load_criteria(path)


def test_criteria_file_cannot_smuggle_an_excluded_element(tmp_path):
    from casesupport.guardrails import ForbiddenField

    path = tmp_path / "bad.yaml"
    path.write_text(
        "benefit_type: T\n"
        "reviewed_by: Someone\n"
        "reviewed_on: 2026-01-01\n"
        "medical_condition: required\n"
        "elements: []\n"
    )
    with pytest.raises(ForbiddenField):
        load_criteria(path)
