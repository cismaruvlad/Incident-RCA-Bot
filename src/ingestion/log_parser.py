"""Parse and normalize raw log data from various sources."""

import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from dateutil import parser as dateutil_parser
import structlog

logger = structlog.get_logger(__name__)


class LogParser:
    """Parses raw log lines and structured log data into a normalized format."""

    # Common log patterns
    SYSLOG_PATTERN = re.compile(
        r"(?P<timestamp>\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+"
        r"(?P<host>\S+)\s+"
        r"(?P<source>\S+?)(?:$$\d+$$)?:\s+"
        r"(?P<message>.*)"
    )

    STANDARD_LOG_PATTERN = re.compile(
        r"(?P<timestamp>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\s+"
        r"(?P<level>DEBUG|INFO|WARN(?:ING)?|ERROR|FATAL|CRITICAL)\s+"
        r"(?:$$(?P<source>[^$$]+)\]\s+)?"
        r"(?P<message>.*)"
    )

    JSON_KEYS_MAP = {
        "ts": "timestamp",
        "time": "timestamp",
        "@timestamp": "timestamp",
        "msg": "message",
        "log": "message",
        "lvl": "level",
        "severity": "level",
        "svc": "source",
        "service": "source",
        "logger": "source",
    }

    def parse_raw_logs(self, raw_logs: str) -> List[Dict[str, Any]]:
        """Parse a block of raw log text into structured entries."""
        lines = raw_logs.strip().split("\n")
        parsed = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            entry = self._parse_line(line)
            if entry:
                parsed.append(entry)
        logger.info("Parsed raw logs", count=len(parsed))
        return parsed

    def parse_structured_logs(self, log_entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalize already-structured log entries."""
        normalized = []
        for entry in log_entries:
            normalized_entry = self._normalize_dict(entry)
            if normalized_entry:
                normalized.append(normalized_entry)
        return normalized

    def _parse_line(self, line: str) -> Optional[Dict[str, Any]]:
        """Attempt to parse a single log line using known patterns."""
        # Try standard log format first
        match = self.STANDARD_LOG_PATTERN.match(line)
        if match:
            return {
                "timestamp": self._parse_timestamp(match.group("timestamp")),
                "level": self._normalize_level(match.group("level")),
                "source": match.group("source") or "application",
                "message": match.group("message"),
                "metadata": {"raw": line},
            }

        # Try syslog format
        match = self.SYSLOG_PATTERN.match(line)
        if match:
            return {
                "timestamp": self._parse_timestamp(match.group("timestamp")),
                "level": self._infer_level(match.group("message")),
                "source": match.group("source"),
                "message": match.group("message"),
                "metadata": {"host": match.group("host"), "raw": line},
            }

        # Fallback: treat entire line as a message
        return {
            "timestamp": datetime.utcnow(),
            "level": self._infer_level(line),
            "source": "unknown",
            "message": line,
            "metadata": {"raw": line},
        }

    def _normalize_dict(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a dictionary log entry to our standard schema."""
        normalized = {}

        # Map known keys
        for raw_key, canonical_key in self.JSON_KEYS_MAP.items():
            if raw_key in entry:
                normalized[canonical_key] = entry[raw_key]

        # Direct keys take precedence
        for key in ("timestamp", "level", "source", "message"):
            if key in entry:
                normalized[key] = entry[key]

        # Ensure required fields
        if "message" not in normalized:
            normalized["message"] = str(entry)
        if "timestamp" not in normalized:
            normalized["timestamp"] = datetime.utcnow()
        else:
            normalized["timestamp"] = self._parse_timestamp(str(normalized["timestamp"]))
        if "level" not in normalized:
            normalized["level"] = self._infer_level(normalized["message"])
        else:
            normalized["level"] = self._normalize_level(str(normalized["level"]))
        if "source" not in normalized:
            normalized["source"] = "unknown"

        # Preserve extra fields as metadata
        standard_keys = {"timestamp", "level", "source", "message"}
        extra = {k: v for k, v in entry.items() if k not in standard_keys and k not in self.JSON_KEYS_MAP}
        normalized["metadata"] = extra if extra else None

        return normalized

    @staticmethod
    def _parse_timestamp(ts_str: str) -> datetime:
        """Parse a timestamp string into a datetime object."""
        try:
            return dateutil_parser.parse(ts_str)
        except (ValueError, TypeError):
            return datetime.utcnow()

    @staticmethod
    def _normalize_level(level: str) -> str:
        """Normalize log level to standard values."""
        level = level.upper().strip()
        mapping = {
            "WARNING": "WARN",
            "FATAL": "CRITICAL",
        }
        return mapping.get(level, level)

    @staticmethod
    def _infer_level(message: str) -> str:
        """Infer log level from message content."""
        msg_lower = message.lower()
        if any(word in msg_lower for word in ["error", "exception", "fail", "panic", "fatal"]):
            return "ERROR"
        if any(word in msg_lower for word in ["warn", "timeout", "retry", "degraded"]):
            return "WARN"
        if any(word in msg_lower for word in ["debug", "trace"]):
            return "DEBUG"
        return "INFO"