"""
Task 006: Event Bus - Payload structure change with multi-consumer propagation

Scenario: An event bus's `emit` method was changed to wrap payloads in an envelope
with routing metadata. Multiple independent consumers (logger, metrics, notifier)
that subscribe to events still unpack the old flat payload format.

Difficulty: Hard
Coupling type: One-to-many contract change (publisher changed, all subscribers break)
"""

from coupled_edit_env.types import TaskInstance


def create_task() -> TaskInstance:
    project_files = {
        "events/bus.py": '''
from typing import Callable
from datetime import datetime
import uuid


class EventEnvelope:
    """Wraps event payload with routing and tracing metadata."""
    def __init__(self, event_type: str, payload: dict, source: str = "system"):
        self.event_id = str(uuid.uuid4())
        self.event_type = event_type
        self.payload = payload
        self.source = source
        self.timestamp = datetime.now().isoformat()
        self.retries = 0

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "payload": self.payload,
            "source": self.source,
            "timestamp": self.timestamp,
            "retries": self.retries,
        }


class EventBus:
    def __init__(self):
        self._subscribers: dict[str, list[Callable]] = {}
        self._history: list[EventEnvelope] = []

    def subscribe(self, event_type: str, handler: Callable):
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    def emit(self, event_type: str, payload: dict, source: str = "system") -> EventEnvelope:
        """
        MODIFIED: Now wraps payload in an EventEnvelope before passing to handlers.
        Previously called handler(event_type, payload) with the raw payload dict.
        Now calls handler(envelope) where envelope is an EventEnvelope instance.

        Returns the envelope for tracking.
        """
        envelope = EventEnvelope(event_type, payload, source)
        self._history.append(envelope)

        for handler in self._subscribers.get(event_type, []):
            handler(envelope)
        for handler in self._subscribers.get("*", []):
            handler(envelope)

        return envelope

    def get_history(self, event_type: str = None) -> list[EventEnvelope]:
        if event_type is None:
            return list(self._history)
        return [e for e in self._history if e.event_type == event_type]
''',
        "events/consumers.py": '''
from events.bus import EventBus


class EventLogger:
    def __init__(self):
        self.logs = []

    def handle(self, event_type: str, payload: dict):
        """Log the event with a formatted message."""
        msg = f"[{event_type}] "
        if "user" in payload:
            msg += f"user={payload['user']} "
        if "action" in payload:
            msg += f"action={payload['action']} "
        if "details" in payload:
            msg += f"details={payload['details']}"
        self.logs.append(msg.strip())

    def get_logs(self) -> list[str]:
        return list(self.logs)


class MetricsCollector:
    def __init__(self):
        self.counters = {}
        self.values = {}

    def handle(self, event_type: str, payload: dict):
        """Track event counts and numeric values."""
        self.counters[event_type] = self.counters.get(event_type, 0) + 1
        if "value" in payload:
            if event_type not in self.values:
                self.values[event_type] = []
            self.values[event_type].append(payload["value"])

    def get_count(self, event_type: str) -> int:
        return self.counters.get(event_type, 0)

    def get_average(self, event_type: str) -> float:
        vals = self.values.get(event_type, [])
        return sum(vals) / len(vals) if vals else 0.0


class AlertNotifier:
    def __init__(self, threshold: float = 100.0):
        self.threshold = threshold
        self.alerts = []

    def handle(self, event_type: str, payload: dict):
        """Generate alerts for high-value events."""
        if "value" in payload and payload["value"] > self.threshold:
            self.alerts.append({
                "event": event_type,
                "value": payload["value"],
                "user": payload.get("user", "unknown"),
                "severity": "high" if payload["value"] > self.threshold * 2 else "medium",
            })

    def get_alerts(self) -> list[dict]:
        return list(self.alerts)

    def clear(self):
        self.alerts = []
''',
        "events/setup.py": '''
from events.bus import EventBus
from events.consumers import EventLogger, MetricsCollector, AlertNotifier


def create_monitored_bus(alert_threshold: float = 100.0) -> tuple:
    """Create a fully wired event bus with all consumers attached."""
    bus = EventBus()
    logger = EventLogger()
    metrics = MetricsCollector()
    alerter = AlertNotifier(threshold=alert_threshold)

    bus.subscribe("*", logger.handle)
    bus.subscribe("*", metrics.handle)
    bus.subscribe("transaction", alerter.handle)
    bus.subscribe("withdrawal", alerter.handle)

    return bus, logger, metrics, alerter
''',
    }

    modified_function = "emit"

    test_suite = '''
import sys
sys.path.insert(0, ".")
from events.bus import EventBus, EventEnvelope


def test_emit_returns_envelope():
    bus = EventBus()
    result = bus.emit("test_event", {"key": "value"}, source="unit_test")
    assert isinstance(result, EventEnvelope)
    assert result.event_type == "test_event"
    assert result.payload == {"key": "value"}
    assert result.source == "unit_test"


def test_emit_stores_history():
    bus = EventBus()
    bus.emit("a", {"x": 1})
    bus.emit("b", {"y": 2})
    assert len(bus.get_history()) == 2
    assert len(bus.get_history("a")) == 1
'''

    hidden_tests = '''
import sys
sys.path.insert(0, ".")
from events.setup import create_monitored_bus


def test_logger_receives_events():
    bus, logger, metrics, alerter = create_monitored_bus()
    bus.emit("login", {"user": "alice", "action": "login"})
    logs = logger.get_logs()
    assert len(logs) == 1
    assert "alice" in logs[0]
    assert "login" in logs[0]


def test_logger_multiple_events():
    bus, logger, metrics, alerter = create_monitored_bus()
    bus.emit("login", {"user": "alice", "action": "login"})
    bus.emit("purchase", {"user": "bob", "action": "buy", "details": "item_123"})
    logs = logger.get_logs()
    assert len(logs) == 2
    assert "bob" in logs[1]


def test_metrics_counts():
    bus, logger, metrics, alerter = create_monitored_bus()
    bus.emit("page_view", {"path": "/home"})
    bus.emit("page_view", {"path": "/about"})
    bus.emit("click", {"target": "button"})
    assert metrics.get_count("page_view") == 2
    assert metrics.get_count("click") == 1


def test_metrics_values():
    bus, logger, metrics, alerter = create_monitored_bus()
    bus.emit("transaction", {"user": "alice", "value": 50.0})
    bus.emit("transaction", {"user": "bob", "value": 150.0})
    assert metrics.get_average("transaction") == 100.0


def test_alerter_fires_on_high_value():
    bus, logger, metrics, alerter = create_monitored_bus(alert_threshold=100.0)
    bus.emit("transaction", {"user": "alice", "value": 50.0})
    bus.emit("transaction", {"user": "bob", "value": 200.0})
    alerts = alerter.get_alerts()
    assert len(alerts) == 1
    assert alerts[0]["user"] == "bob"
    assert alerts[0]["value"] == 200.0


def test_alerter_severity_levels():
    bus, logger, metrics, alerter = create_monitored_bus(alert_threshold=100.0)
    bus.emit("withdrawal", {"user": "eve", "value": 150.0})
    bus.emit("withdrawal", {"user": "mal", "value": 250.0})
    alerts = alerter.get_alerts()
    assert len(alerts) == 2
    severities = [a["severity"] for a in alerts]
    assert "medium" in severities
    assert "high" in severities


def test_no_alert_below_threshold():
    bus, logger, metrics, alerter = create_monitored_bus(alert_threshold=100.0)
    bus.emit("transaction", {"user": "small", "value": 10.0})
    assert len(alerter.get_alerts()) == 0


def test_full_integration():
    bus, logger, metrics, alerter = create_monitored_bus(alert_threshold=50.0)
    bus.emit("transaction", {"user": "alice", "value": 30.0, "action": "deposit"})
    bus.emit("transaction", {"user": "bob", "value": 75.0, "action": "deposit"})
    bus.emit("login", {"user": "charlie", "action": "login"})

    assert len(logger.get_logs()) == 3
    assert metrics.get_count("transaction") == 2
    assert metrics.get_count("login") == 1
    assert len(alerter.get_alerts()) == 1
'''

    ground_truth_repairs = {
        "events/consumers.py": "All handle methods must accept a single envelope arg and access envelope.event_type, envelope.payload['field'], etc.",
    }

    return TaskInstance(
        task_id="task_006_event_bus",
        instruction=(
            "The `emit` method in events/bus.py was intentionally changed. "
            "It now wraps payloads in an EventEnvelope and passes the envelope to handlers "
            "as a single argument: handler(envelope). Previously it called handler(event_type, payload). "
            "This change is correct and must NOT be reverted. "
            "Fix all consumer handle methods in events/consumers.py to accept the new "
            "envelope format and extract event_type and payload from it."
        ),
        project_files=project_files,
        modified_function=modified_function,
        test_suite=test_suite,
        hidden_tests=hidden_tests,
        ground_truth_repairs=ground_truth_repairs,
        difficulty="hard",
        revert_indicators=[
            "handler(event_type, payload)",
            "handler(event_type=event_type",
        ],
        modified_is_async=False,
    )
