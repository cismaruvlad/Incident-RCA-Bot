"""OpenTelemetry log and trace collector integration."""

from datetime import datetime
from typing import List, Dict, Any, Optional
import structlog

logger = structlog.get_logger(__name__)


class OTelLogCollector:
    """
    Collects and normalizes OpenTelemetry log records and span data.
    In production, this would connect to an OTLP receiver or query a log backend.
    For the MVP, it processes OTLP-formatted log/span data passed directly.
    """

    def parse_otel_logs(self, otel_log_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Parse OpenTelemetry LogRecord format.

        Expected OTLP LogRecord fields:
        - timeUnixNano / observedTimeUnixNano
        - severityText / severityNumber
        - body (stringValue / kvlistValue)
        - resource.attributes
        - attributes
        - traceId, spanId
        """
        parsed = []
        for record in otel_log_records:
            entry = self._parse_log_record(record)
            if entry:
                parsed.append(entry)
        logger.info("Parsed OTel log records", count=len(parsed))
        return parsed

    def parse_otel_spans(self, spans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Parse OpenTelemetry span data into log-like entries
        (useful for understanding request flow during an incident).
        """
        parsed = []
        for span in spans:
            entry = self._parse_span(span)
            if entry:
                parsed.append(entry)
        logger.info("Parsed OTel spans", count=len(parsed))
        return parsed

    def _parse_log_record(self, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Convert a single OTLP LogRecord to our normalized format."""
        try:
            # Timestamp
            time_nano = record.get("timeUnixNano") or record.get("observedTimeUnixNano")
            if time_nano:
                timestamp = datetime.utcfromtimestamp(int(time_nano) / 1e9)
            else:
                timestamp = datetime.utcnow()

            # Severity
            level = record.get("severityText", "INFO").upper()

            # Body / message
            body = record.get("body", {})
            if isinstance(body, dict):
                message = body.get("stringValue", str(body))
            else:
                message = str(body)

            # Source from resource attributes
            resource_attrs = self._flatten_attributes(
                record.get("resource", {}).get("attributes", [])
            )
            source = resource_attrs.get("service.name", "unknown")

            # Extra attributes
            log_attrs = self._flatten_attributes(record.get("attributes", []))
            metadata = {
                **resource_attrs,
                **log_attrs,
            }

            # Trace context
            trace_id = record.get("traceId")
            span_id = record.get("spanId")
            if trace_id:
                metadata["trace_id"] = trace_id
            if span_id:
                metadata["span_id"] = span_id

            return {
                "timestamp": timestamp,
                "level": level,
                "source": source,
                "message": message,
                "metadata": metadata,
            }
        except Exception as e:
            logger.warning("Failed to parse OTel log record", error=str(e))
            return None

    def _parse_span(self, span: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Convert a span to a log-like entry focusing on errors and high latency."""
        try:
            name = span.get("name", "unknown_operation")
            status = span.get("status", {})
            status_code = status.get("code", 0)  # 0=UNSET, 1=OK, 2=ERROR

            start_nano = span.get("startTimeUnixNano", 0)
            end_nano = span.get("endTimeUnixNano", 0)
            duration_ms = (int(end_nano) - int(start_nano)) / 1e6

            timestamp = datetime.utcfromtimestamp(int(start_nano) / 1e9) if start_nano else datetime.utcnow()

            # Determine level
            if status_code == 2:
                level = "ERROR"
            elif duration_ms > 5000:
                level = "WARN"
            else:
                level = "INFO"

            resource_attrs = self._flatten_attributes(
                span.get("resource", {}).get("attributes", [])
            )
            span_attrs = self._flatten_attributes(span.get("attributes", []))

            message = f"Span '{name}' duration={duration_ms:.1f}ms status={status.get('message', 'OK')}"
            if status_code == 2:
                message = f"ERROR in span '{name}': {status.get('message', 'unknown error')} (duration={duration_ms:.1f}ms)"

            return {
                "timestamp": timestamp,
                "level": level,
                "source": resource_attrs.get("service.name", "unknown"),
                "message": message,
                "metadata": {
                    "trace_id": span.get("traceId"),
                    "span_id": span.get("spanId"),
                    "parent_span_id": span.get("parentSpanId"),
                    "duration_ms": duration_ms,
                    "span_name": name,
                    **span_attrs,
                },
            }
        except Exception as e:
            logger.warning("Failed to parse OTel span", error=str(e))
            return None

    @staticmethod
    def _flatten_attributes(attrs: list) -> Dict[str, Any]:
        """Flatten OTLP key-value attribute list to dict."""
        result = {}
        if not isinstance(attrs, list):
            return result
        for attr in attrs:
            key = attr.get("key", "")
            value = attr.get("value", {})
            if isinstance(value, dict):
                # OTLP uses typed values like stringValue, intValue, etc.
                for v_key in ("stringValue", "intValue", "doubleValue", "boolValue"):
                    if v_key in value:
                        result[key] = value[v_key]
                        break
                else:
                    result[key] = str(value)
            else:
                result[key] = value
        return result