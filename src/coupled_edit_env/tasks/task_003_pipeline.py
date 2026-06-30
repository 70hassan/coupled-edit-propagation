"""
Task 003: Data Pipeline - Output format change propagation

Scenario: A data pipeline where `transform_records` was changed from yielding
flat dicts to yielding nested dicts with metadata. Downstream aggregation and
serialization code breaks because it accesses fields at the wrong nesting level.

Difficulty: Medium
Coupling type: Data shape contract change across module boundary
"""

from coupled_edit_env.types import TaskInstance


def create_task() -> TaskInstance:
    project_files = {
        "pipeline/transform.py": '''
from datetime import datetime


class RecordTransformer:
    def __init__(self, source_name: str):
        self.source_name = source_name
        self._processed_count = 0

    def transform_records(self, raw_records: list[dict]) -> list[dict]:
        """
        MODIFIED: Now wraps each record in a metadata envelope.
        Previously returned flat dicts like {"name": ..., "value": ..., "timestamp": ...}.
        Now returns: {"meta": {"source": str, "seq": int, "processed_at": str},
                      "data": {original flat fields}}
        """
        results = []
        for record in raw_records:
            self._processed_count += 1
            enriched = {
                "meta": {
                    "source": self.source_name,
                    "seq": self._processed_count,
                    "processed_at": datetime.now().isoformat(),
                },
                "data": {
                    "name": record.get("name", "unknown"),
                    "value": float(record.get("value", 0)),
                    "timestamp": record.get("ts", datetime.now().isoformat()),
                    "category": record.get("cat", "uncategorized"),
                },
            }
            results.append(enriched)
        return results

    @property
    def processed_count(self) -> int:
        return self._processed_count
''',
        "pipeline/aggregate.py": '''
from pipeline.transform import RecordTransformer


class Aggregator:
    def __init__(self, transformer: RecordTransformer):
        self.transformer = transformer

    def sum_by_category(self, records: list[dict]) -> dict[str, float]:
        """Sum values grouped by category."""
        transformed = self.transformer.transform_records(records)
        totals = {}
        for item in transformed:
            cat = item["category"]
            totals[cat] = totals.get(cat, 0) + item["value"]
        return totals

    def average_value(self, records: list[dict]) -> float:
        """Compute average value across all records."""
        transformed = self.transformer.transform_records(records)
        if not transformed:
            return 0.0
        total = sum(item["value"] for item in transformed)
        return total / len(transformed)

    def latest_by_category(self, records: list[dict]) -> dict[str, dict]:
        """Get the most recent record per category."""
        transformed = self.transformer.transform_records(records)
        latest = {}
        for item in transformed:
            cat = item["category"]
            if cat not in latest or item["timestamp"] > latest[cat]["timestamp"]:
                latest[cat] = item
        return latest

    def filter_above_threshold(self, records: list[dict], threshold: float) -> list[dict]:
        """Return only records with value above threshold."""
        transformed = self.transformer.transform_records(records)
        return [item for item in transformed if item["value"] > threshold]
''',
        "pipeline/export.py": '''
import json
from pipeline.transform import RecordTransformer


class CsvExporter:
    def __init__(self, transformer: RecordTransformer):
        self.transformer = transformer

    def to_csv_rows(self, records: list[dict]) -> list[str]:
        """Convert records to CSV format lines."""
        transformed = self.transformer.transform_records(records)
        rows = ["name,value,category,timestamp"]
        for item in transformed:
            row = f"{item['name']},{item['value']},{item['category']},{item['timestamp']}"
            rows.append(row)
        return rows

    def to_json_summary(self, records: list[dict]) -> str:
        """Produce a JSON summary with record count and value stats."""
        transformed = self.transformer.transform_records(records)
        values = [item["value"] for item in transformed]
        summary = {
            "count": len(transformed),
            "total_value": sum(values),
            "min_value": min(values) if values else 0,
            "max_value": max(values) if values else 0,
            "source": transformed[0]["name"] if transformed else "none",
        }
        return json.dumps(summary)
''',
    }

    modified_function = "transform_records"

    test_suite = '''
import sys
sys.path.insert(0, ".")
from pipeline.transform import RecordTransformer


def test_transform_returns_envelope():
    t = RecordTransformer("test_source")
    raw = [{"name": "sensor_a", "value": "42.5", "ts": "2024-01-01T00:00:00", "cat": "temperature"}]
    result = t.transform_records(raw)
    assert len(result) == 1
    assert "meta" in result[0]
    assert "data" in result[0]
    assert result[0]["data"]["name"] == "sensor_a"
    assert result[0]["data"]["value"] == 42.5
    assert result[0]["meta"]["source"] == "test_source"
    assert result[0]["meta"]["seq"] == 1
'''

    hidden_tests = '''
import sys, json
sys.path.insert(0, ".")
from pipeline.transform import RecordTransformer
from pipeline.aggregate import Aggregator
from pipeline.export import CsvExporter


SAMPLE_RECORDS = [
    {"name": "temp_1", "value": "20.0", "ts": "2024-01-01T10:00:00", "cat": "temperature"},
    {"name": "temp_2", "value": "25.0", "ts": "2024-01-01T11:00:00", "cat": "temperature"},
    {"name": "hum_1", "value": "60.0", "ts": "2024-01-01T10:00:00", "cat": "humidity"},
    {"name": "hum_2", "value": "40.0", "ts": "2024-01-01T12:00:00", "cat": "humidity"},
]


def test_sum_by_category():
    t = RecordTransformer("sensor_net")
    agg = Aggregator(t)
    result = agg.sum_by_category(SAMPLE_RECORDS)
    assert result["temperature"] == 45.0
    assert result["humidity"] == 100.0


def test_average_value():
    t = RecordTransformer("sensor_net")
    agg = Aggregator(t)
    result = agg.average_value(SAMPLE_RECORDS)
    assert abs(result - 36.25) < 0.01


def test_average_value_empty():
    t = RecordTransformer("x")
    agg = Aggregator(t)
    assert agg.average_value([]) == 0.0


def test_latest_by_category():
    t = RecordTransformer("sensor_net")
    agg = Aggregator(t)
    result = agg.latest_by_category(SAMPLE_RECORDS)
    assert "temperature" in result
    assert "humidity" in result
    assert result["temperature"]["data"]["name"] == "temp_2" or result["temperature"].get("name") == "temp_2"


def test_filter_above_threshold():
    t = RecordTransformer("sensor_net")
    agg = Aggregator(t)
    result = agg.filter_above_threshold(SAMPLE_RECORDS, 30.0)
    assert len(result) == 2


def test_csv_export():
    t = RecordTransformer("sensor_net")
    exp = CsvExporter(t)
    rows = exp.to_csv_rows(SAMPLE_RECORDS)
    assert rows[0] == "name,value,category,timestamp"
    assert "temp_1" in rows[1]
    assert "20.0" in rows[1]


def test_json_summary():
    t = RecordTransformer("sensor_net")
    exp = CsvExporter(t)
    result = json.loads(exp.to_json_summary(SAMPLE_RECORDS))
    assert result["count"] == 4
    assert result["total_value"] == 145.0
    assert result["min_value"] == 20.0
    assert result["max_value"] == 60.0
'''

    ground_truth_repairs = {
        "pipeline/aggregate.py": "All methods must access item['data']['category'], item['data']['value'], item['data']['timestamp'] instead of item['category'], etc.",
        "pipeline/export.py": "Must access item['data']['name'], item['data']['value'], etc. and item['meta'] for source info.",
    }

    return TaskInstance(
        task_id="task_003_pipeline",
        instruction=(
            "The function `transform_records` in pipeline/transform.py was intentionally changed. "
            "It now wraps each record in a metadata envelope: {'meta': {...}, 'data': {original fields}}. "
            "Previously it returned flat dicts with fields at the top level. "
            "This change is correct and must NOT be reverted. "
            "Fix all downstream code in pipeline/aggregate.py and pipeline/export.py that still "
            "accesses fields as if they were at the top level of each record."
        ),
        project_files=project_files,
        modified_function=modified_function,
        test_suite=test_suite,
        hidden_tests=hidden_tests,
        ground_truth_repairs=ground_truth_repairs,
        difficulty="medium",
        revert_indicators=[
            "'name': record.get",
            '"name": record.get',
        ],
        modified_is_async=False,
    )
