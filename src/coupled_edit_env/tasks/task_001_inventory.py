"""
Task 001: Inventory System - Return type change propagation

Scenario: An inventory system where `get_stock_level` was changed from returning
an integer to returning a dict with quantity and warehouse info. Several downstream
functions that called it and assumed an integer return are now broken.

Difficulty: Easy
Coupling type: Return-type contract change
"""

from coupled_edit_env.types import TaskInstance


def create_task() -> TaskInstance:
    project_files = {
        "inventory/stock.py": '''
class Warehouse:
    def __init__(self, name: str, location: str):
        self.name = name
        self.location = location


class StockManager:
    def __init__(self):
        self._inventory = {}
        self._warehouses = {
            "main": Warehouse("Main Depot", "Building A"),
            "overflow": Warehouse("Overflow", "Building C"),
        }

    def add_item(self, sku: str, quantity: int, warehouse: str = "main"):
        if sku not in self._inventory:
            self._inventory[sku] = []
        self._inventory[sku].append({"qty": quantity, "warehouse": warehouse})

    def get_stock_level(self, sku: str) -> dict:
        """
        MODIFIED: Now returns a dict with breakdown by warehouse.
        Previously returned a plain integer total.

        Returns:
            {"total": int, "breakdown": {warehouse_name: quantity}}
        """
        if sku not in self._inventory:
            return {"total": 0, "breakdown": {}}

        breakdown = {}
        total = 0
        for entry in self._inventory[sku]:
            wh = entry["warehouse"]
            breakdown[wh] = breakdown.get(wh, 0) + entry["qty"]
            total += entry["qty"]
        return {"total": total, "breakdown": breakdown}

    def is_available(self, sku: str, requested: int) -> bool:
        """Check if enough stock exists to fulfill a request."""
        level = self.get_stock_level(sku)
        return level >= requested

    def reorder_check(self, sku: str, threshold: int = 10) -> str:
        """Return a reorder recommendation based on current stock."""
        current = self.get_stock_level(sku)
        if current == 0:
            return "CRITICAL: Out of stock"
        elif current < threshold:
            return f"LOW: Only {current} units remaining"
        else:
            return "OK: Stock sufficient"

    def transfer_needed(self, sku: str, target_warehouse: str, needed: int) -> int:
        """Calculate how many units need transferring to meet demand."""
        current = self.get_stock_level(sku)
        deficit = needed - current
        return max(0, deficit)
''',
        "inventory/orders.py": '''
from inventory.stock import StockManager


class OrderProcessor:
    def __init__(self, stock: StockManager):
        self.stock = stock
        self.orders = []

    def place_order(self, sku: str, quantity: int) -> dict:
        """Place an order if stock is available."""
        if not self.stock.is_available(sku, quantity):
            return {"status": "rejected", "reason": "insufficient stock"}

        self.orders.append({"sku": sku, "qty": quantity})
        return {"status": "accepted", "order_id": len(self.orders)}

    def bulk_availability_report(self, items: list[tuple[str, int]]) -> list[dict]:
        """Check availability for multiple items at once."""
        report = []
        for sku, qty in items:
            available = self.stock.is_available(sku, qty)
            level = self.stock.get_stock_level(sku)
            report.append({
                "sku": sku,
                "requested": qty,
                "in_stock": level,
                "can_fulfill": available,
            })
        return report
''',
    }

    modified_function = "get_stock_level"

    test_suite = '''
import sys
sys.path.insert(0, ".")
from inventory.stock import StockManager
from inventory.orders import OrderProcessor


def test_stock_level_returns_dict():
    sm = StockManager()
    sm.add_item("SKU001", 5, "main")
    sm.add_item("SKU001", 3, "overflow")
    result = sm.get_stock_level("SKU001")
    assert isinstance(result, dict)
    assert result["total"] == 8
    assert result["breakdown"]["main"] == 5
    assert result["breakdown"]["overflow"] == 3


def test_stock_level_empty():
    sm = StockManager()
    result = sm.get_stock_level("MISSING")
    assert result == {"total": 0, "breakdown": {}}
'''

    hidden_tests = '''
import sys
sys.path.insert(0, ".")
from inventory.stock import StockManager
from inventory.orders import OrderProcessor


def test_is_available_with_dict_return():
    sm = StockManager()
    sm.add_item("SKU001", 15, "main")
    assert sm.is_available("SKU001", 10) is True
    assert sm.is_available("SKU001", 20) is False


def test_is_available_zero_stock():
    sm = StockManager()
    assert sm.is_available("EMPTY", 1) is False


def test_reorder_check_critical():
    sm = StockManager()
    assert sm.reorder_check("MISSING") == "CRITICAL: Out of stock"


def test_reorder_check_low():
    sm = StockManager()
    sm.add_item("SKU002", 5, "main")
    result = sm.reorder_check("SKU002")
    assert "LOW" in result
    assert "5" in result


def test_reorder_check_ok():
    sm = StockManager()
    sm.add_item("SKU003", 50, "main")
    assert sm.reorder_check("SKU003") == "OK: Stock sufficient"


def test_transfer_needed_calculation():
    sm = StockManager()
    sm.add_item("SKU004", 7, "main")
    assert sm.transfer_needed("SKU004", "overflow", 10) == 3
    assert sm.transfer_needed("SKU004", "overflow", 5) == 0


def test_order_placement_integrated():
    sm = StockManager()
    sm.add_item("WIDGET", 20, "main")
    op = OrderProcessor(sm)
    result = op.place_order("WIDGET", 15)
    assert result["status"] == "accepted"


def test_order_rejected_insufficient():
    sm = StockManager()
    sm.add_item("WIDGET", 3, "main")
    op = OrderProcessor(sm)
    result = op.place_order("WIDGET", 10)
    assert result["status"] == "rejected"


def test_bulk_report_uses_total():
    sm = StockManager()
    sm.add_item("A", 10, "main")
    sm.add_item("B", 2, "overflow")
    op = OrderProcessor(sm)
    report = op.bulk_availability_report([("A", 5), ("B", 5)])
    assert report[0]["in_stock"] == 10 or report[0]["in_stock"] == {"total": 10, "breakdown": {"main": 10}}
    assert report[0]["can_fulfill"] is True
    assert report[1]["can_fulfill"] is False
'''

    ground_truth_repairs = {
        "inventory/stock.py": "is_available uses level['total'], reorder_check uses current['total'], transfer_needed uses current['total']",
    }

    return TaskInstance(
        task_id="task_001_inventory",
        instruction=(
            "The function `get_stock_level` in inventory/stock.py was intentionally changed. "
            "It now returns a dict like {'total': int, 'breakdown': {warehouse: qty}} instead of a plain integer. "
            "This change is correct and must NOT be reverted. However, several other functions in the same file "
            "and in inventory/orders.py still assume it returns an integer. "
            "Find and fix all the downstream code that breaks because of this change."
        ),
        project_files=project_files,
        modified_function=modified_function,
        test_suite=test_suite,
        hidden_tests=hidden_tests,
        ground_truth_repairs=ground_truth_repairs,
        difficulty="easy",
        revert_indicators=[
            "return total\n",
            "-> int:",
            "return 0\n        breakdown",
        ],
        modified_is_async=False,
    )
