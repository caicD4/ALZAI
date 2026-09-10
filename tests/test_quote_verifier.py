from tools.quote_verifier import QuoteVerifier, verify_quote


def test_quote_verifier_exact_match():
    source = "According to MIT Sloan research, only 11% of organizations surveyed reported significant returns."
    quote = "only 11% of organizations surveyed reported significant returns"

    assert verify_quote(quote, source) is True
    assert QuoteVerifier.verify(quote, source) is True


def test_quote_verifier_normalized_whitespace_and_case():
    source = """
    According to MIT Sloan research,
    only 11% of organizations   surveyed reported
    significant returns.
    """
    quote = "Only 11% of organizations surveyed reported significant returns."

    assert verify_quote(quote, source) is True


def test_quote_verifier_smart_quotes_and_dashes():
    source = "The study noted—“only 11% of organizations’ projects succeeded”—which surprised analysts."
    quote = 'only 11% of organizations\' projects succeeded'

    assert verify_quote(quote, source) is True


def test_quote_verifier_punctuation_insensitivity():
    source = "Only 11% of organizations (surveyed in 2023) reported high ROI."
    quote = "only 11 of organizations surveyed in 2023 reported high ROI"

    assert verify_quote(quote, source) is True


def test_quote_verifier_fabrication_fails():
    source = "Only 11% of organizations surveyed reported significant returns."
    fake_quote = "Over 90% of organizations reported massive failures across all teams."

    assert verify_quote(fake_quote, source) is False


def test_quote_verifier_empty_inputs():
    assert verify_quote("", "some text") is False
    assert verify_quote("some quote", "") is False
    assert verify_quote("   ", "   ") is False
