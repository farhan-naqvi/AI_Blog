import json
import logging

from signalwatch.logging import JsonFormatter, configure_logging


def test_formatter_omits_database_identifiers() -> None:
    record = logging.LogRecord("test", logging.INFO, "", 0, "request_complete", (), None)
    record.source_id = "source-secret-id"
    record.job_id = "job-secret-id"
    record.subsystem = "repository"
    record.status_code = 200
    payload = json.loads(JsonFormatter().format(record))
    assert payload["subsystem"] == "repository"
    assert payload["status_code"] == 200
    assert "source_id" not in payload and "job_id" not in payload


def test_rate_limit_log_keeps_wait_but_omits_url_and_authorization() -> None:
    record = logging.LogRecord("test", logging.WARNING, "", 0, "collector_rate_limited", (), None)
    record.subsystem = "collector:github"
    record.category = "rate_limit"
    record.wait_seconds = 2
    record.url = "https://api.example.test/private?token=secret"
    record.authorization = "Bearer secret"
    payload = json.loads(JsonFormatter().format(record))
    assert payload["wait_seconds"] == 2
    assert "url" not in payload and "authorization" not in payload


def test_http_client_request_logging_is_suppressed() -> None:
    configure_logging("INFO")
    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("httpcore").level == logging.WARNING
