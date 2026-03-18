"""Parse and normalize alert data from monitoring systems."""

from datetime import datetime
from typing import List, Dict, Any, Optional
from dateutil import parser as dateutil_parser
import structlog

logger = structlog.get_logger(__name__)


class AlertParser:
    """Parses alerts from various monitoring systems (Prometheus, PagerDuty, Datadog, etc.)."""

    # Known alert source schemas
    PROMETHEUS_KEYS = {"alertname", "status", "startsAt", "endsAt", "labels", "annotations"}
    PAGERDUTY_KEYS = {"incident_number", "title", "urgency", "created_at", "resolved_at"}
    DATADOG_KEYS = {"alert_id", "title", "alert_type", "date_happened"}

    def parse_alerts(self, raw_alerts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse a list of raw alert dictionaries into normalized format."""
        normalized = []
        for alert in raw_alerts:
            parsed = self._detect_and_parse(alert)
            if parsed:
                normalized.append(parsed)
        logger.info("Parsed alerts", count=len(normalized))
        return normalized

    def _detect_and_parse(self, alert: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Auto-detect alert source and parse accordingly."""
        keys = set(alert.keys())

        if keys & self.PROMETHEUS_KEYS:
            return self._parse_prometheus(alert)
        elif keys & self.PAGERDUTY_KEYS:
            return self._parse_pagerduty(alert)
        elif keys & self.DATADOG_KEYS:
            return self._parse_datadog(alert)
        else:
            return self._parse_generic(alert)

    def _parse_prometheus(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})
        return {
            "alert_name": alert.get("alertname") or labels.get("alertname", "Unknown"),
            "source": "prometheus",
            "severity": labels.get("severity", "warning"),
            "triggered_at": self._parse_ts(alert.get("startsAt")),
            "resolved_at": self._parse_ts(alert.get("endsAt")),
            "description": annotations.get("description") or annotations.get("summary", ""),
            "labels": labels,
        }

    def _parse_pagerduty(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "alert_name": alert.get("title", "PagerDuty Incident"),
            "source": "pagerduty",
            "severity": self._map_pagerduty_urgency(alert.get("urgency")),
            "triggered_at": self._parse_ts(alert.get("created_at")),
            "resolved_at": self._parse_ts(alert.get("resolved_at")),
            "description": alert.get("description", ""),
            "labels": {"incident_number": alert.get("incident_number")},
        }

    def _parse_datadog(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "alert_name": alert.get("title", "Datadog Alert"),
            "source": "datadog",
            "severity": alert.get("alert_type", "warning"),
            "triggered_at": self._parse_ts(alert.get("date_happened")),
            "resolved_at": None,
            "description": alert.get("body", ""),
            "labels": {"alert_id": alert.get("alert_id")},
        }

    def _parse_generic(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "alert_name": alert.get("alert_name") or alert.get("name") or alert.get("title", "Unknown Alert"),
            "source": alert.get("source", "unknown"),
            "severity": alert.get("severity", "warning"),
            "triggered_at": self._parse_ts(
                alert.get("triggered_at") or alert.get("timestamp") or alert.get("created_at")
            ),
            "resolved_at": self._parse_ts(alert.get("resolved_at")),
            "description": alert.get("description") or alert.get("message", ""),
            "labels": alert.get("labels", {}),
        }

    @staticmethod
    def _parse_ts(ts_value: Any) -> Optional[datetime]:
        if ts_value is None:
            return None
        if isinstance(ts_value, datetime):
            return ts_value
        if isinstance(ts_value, (int, float)):
            return datetime.utcfromtimestamp(ts_value)
        try:
            return dateutil_parser.parse(str(ts_value))
        except (ValueError, TypeError):
            return datetime.utcnow()

    @staticmethod
    def _map_pagerduty_urgency(urgency: Optional[str]) -> str:
        mapping = {"high": "critical", "low": "warning"}
        return mapping.get(urgency or "", "warning")