"""Tests for data ingestion and parsing."""

import pytest
from datetime import datetime
from src.ingestion.log_parser import LogParser
from src.ingestion.alert_parser import AlertParser
from src.ingestion.otel_collector import OTelLogCollector


class TestLogParser:
    """Tests for LogParser."""

    def setup_method(self):
        self.parser = LogParser()

    def test_parse_raw_logs_standard_format(self, sample_raw_logs):
        result = self.parser.parse_raw_logs(sample_raw_logs)
        assert len(result) > 0

        # Check that errors are detected
        error_entries = [e for e in result if e["level"] == "ERROR"]
        assert len(error_entries) >= 3

        # Check source extraction
        sources = {e["source"] for e in result}
        assert "payment-service" in sources or any("payment" in s for s in sources)

    def test_parse_structured_logs(self, sample_logs):
        result = self.parser.parse_structured_logs(sample_logs)
        assert len(result) == len(sample_logs)

        for entry in result:
            assert "timestamp" in entry
            assert "level" in entry
            assert "source" in entry
            assert "message" in entry

    def test_parse_empty_logs(self):
        result = self.parser.parse_raw_logs("")
        assert result == []

    def test_infer_level_error(self):
        level = LogParser._infer_level("java.lang.NullPointerException at line 42")
        assert level == "ERROR"

    def test_infer_level_warn(self):
        level = LogParser._infer_level("Connection timeout after 30s, retrying...")
        assert level == "WARN"

    def test_infer_level_info(self):
        level = LogParser._infer_level("Server started on port 8080")
        assert level == "INFO"

    def test_normalize_level(self):
        assert LogParser._normalize_level("WARNING") == "WARN"
        assert LogParser._normalize_level("FATAL") == "CRITICAL"
        assert LogParser._normalize_level("ERROR") == "ERROR"


class TestAlertParser:
    """Tests for AlertParser."""

    def setup_method(self):
        self.parser = AlertParser()

    def test_parse_mixed_alerts(self, sample_alerts):
        result = self.parser.parse_alerts(sample_alerts)
        assert len(result) == len(sample_alerts)

        for alert in result:
            assert "alert_name" in alert
            assert "source" in alert
            assert "triggered_at" in alert

    def test_parse_prometheus_alert(self):