from estimator import tokenizer


def test_approx_count_is_chars_over_four():
    # Fallback approximation: ~4 chars/token, min 1 for non-empty.
    assert tokenizer.approx_count("") == 0
    assert tokenizer.approx_count("a" * 8) == 2
    assert tokenizer.approx_count("abc") == 1  # rounds up to at least 1


def test_count_tokens_unknown_provider_uses_approx():
    text = "x" * 40
    assert tokenizer.count_tokens(text, provider="mystery") == tokenizer.approx_count(text)
