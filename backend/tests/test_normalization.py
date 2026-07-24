from signalwatch.normalization import canonicalize_url, content_fingerprint, normalize_title


def test_canonicalize_url_removes_tracking_and_fragment() -> None:
    assert canonicalize_url("HTTPS://Example.COM:443//news/item/?utm_source=x&b=2&a=1#top") == "https://example.com/news/item?a=1&b=2"


def test_content_fingerprint_is_stable_for_whitespace_and_case() -> None:
    assert content_fingerprint(" Model  Release ", "A  result") == content_fingerprint("model release", "a result")


def test_normalize_title_collapses_whitespace() -> None:
    assert normalize_title("  one\n two\tthree ") == "one two three"
