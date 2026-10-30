from casesupport.provenance import UNKNOWN, Sourced, Unknown, normalize, quote_matches

DOC = (
    "The applicant states that she entered the United States on 3 March 2019 "
    "through the port of entry at San Ysidro, California."
)


def test_quote_matches_verbatim():
    assert quote_matches(DOC, "entered the United States on 3 March 2019")


def test_quote_matches_across_whitespace_and_unicode_noise():
    # What PDF extraction and OCR actually do to a quote.
    assert quote_matches(DOC, "entered  the\nUnited   States on 3 March 2019")
    assert quote_matches(DOC, "port of entry at San­Ysidro, California".replace("­", " "))


def test_quote_does_not_match_fabrication():
    assert not quote_matches(DOC, "entered the United States on 3 March 2017")
    assert not quote_matches(DOC, "the applicant has no criminal history")


def test_short_quotes_are_rejected_as_evidence():
    # "the" appears in the document but locates nothing.
    assert not quote_matches(DOC, "the")
    assert not quote_matches(DOC, "states")


def test_verified_against_sets_flag():
    candidate = Sourced("2019-03-03", "D1", 1, "entered the United States on 3 March 2019")
    assert candidate.verified is False
    verified = candidate.verified_against(DOC)
    assert isinstance(verified, Sourced)
    assert verified.verified is True
    assert verified.value == "2019-03-03"


def test_fabricated_quote_collapses_to_unknown():
    candidate = Sourced("2017-03-03", "D1", 1, "entered the United States on 3 March 2017")
    assert candidate.verified_against(DOC) is UNKNOWN


def test_unverified_value_does_not_leak():
    candidate = Sourced("2019-03-03", "D1", 1, "some quote")
    assert candidate.value_or_unknown() is UNKNOWN


def test_unknown_is_falsy_singleton():
    assert not UNKNOWN
    assert Unknown() is UNKNOWN
    assert repr(UNKNOWN) == "UNKNOWN"


def test_normalize_is_idempotent():
    assert normalize(normalize(DOC)) == normalize(DOC)
