import pytest

from signalwatch.security import validate_public_url


@pytest.mark.parametrize("url", ["http://127.0.0.1/admin", "http://localhost/private", "file:///etc/passwd"])
def test_ssrf_guard_rejects_local_or_non_http_urls(url: str) -> None:
    with pytest.raises(ValueError):
        validate_public_url(url)
