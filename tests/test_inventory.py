from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.inventory.models import InventoryRecord
from app.inventory.repository import InventoryRepository

ROOT = Path(__file__).resolve().parent.parent
INVENTORY_PATH = ROOT / "data" / "inventory.json"

STABLE_IDS = (
    "inv_indiranagar_cola_500ml",
    "inv_metro_fresh_cola_500ml",
    "inv_city_corner_juice_1l",
)


def _write(tmp_path: Path, payload: object) -> Path:
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_existing_store_and_product_return_correct_stock() -> None:
    repo = InventoryRepository(INVENTORY_PATH)
    indiranagar_cola = repo.find("Indiranagar Mart", "Cola 500ml")
    metro_cola = repo.find("Metro Fresh", "cola 500ml")
    city_juice = repo.find("City Corner", "Juice 1L")

    assert indiranagar_cola is not None and indiranagar_cola.units == 0
    assert metro_cola is not None and metro_cola.units == 48
    assert city_juice is not None and city_juice.units == 12


def test_unknown_store_or_product_returns_defined_result() -> None:
    repo = InventoryRepository(INVENTORY_PATH)

    assert repo.find("Unknown Store", "Cola 500ml") is None
    assert repo.find("Metro Fresh", "Unknown Product") is None
    assert repo.find_by_store("Does Not Exist") == []
    assert repo.find_by_product("Does Not Exist") == []
    assert repo.get("inv_does_not_exist") is None


def test_record_ids_remain_stable() -> None:
    repo = InventoryRepository(INVENTORY_PATH)
    ids_before = tuple(record.id for record in repo.all())
    assert ids_before == STABLE_IDS

    repo.find("Indiranagar Mart", "Cola 500ml")
    repo.find_by_product("Cola 500ml")
    repo.find_by_store("City Corner")
    repo.get("inv_metro_fresh_cola_500ml")

    ids_after = tuple(record.id for record in repo.all())
    assert ids_after == STABLE_IDS
    assert repo.get("inv_indiranagar_cola_500ml").id == "inv_indiranagar_cola_500ml"
    assert repo.get("inv_metro_fresh_cola_500ml").id == "inv_metro_fresh_cola_500ml"
    assert repo.get("inv_city_corner_juice_1l").id == "inv_city_corner_juice_1l"


def test_missing_file_fails_safely(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        InventoryRepository(tmp_path / "missing.json")


def test_malformed_json_fails_safely(tmp_path: Path) -> None:
    path = tmp_path / "inventory.json"
    path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(ValueError, match="malformed"):
        InventoryRepository(path)


def test_non_list_json_fails_safely(tmp_path: Path) -> None:
    path = _write(tmp_path, {"id": "inv_x"})
    with pytest.raises(ValueError, match="list"):
        InventoryRepository(path)


def test_duplicate_ids_fail_safely(tmp_path: Path) -> None:
    record = {
        "id": "inv_dup",
        "store": "Store A",
        "product": "Cola 500ml",
        "units": 1,
    }
    path = _write(tmp_path, [record, {**record, "units": 2}])
    with pytest.raises(ValueError, match="Duplicate"):
        InventoryRepository(path)


@pytest.mark.parametrize(
    "payload",
    [
        {"id": "inv_x", "store": "Store A", "product": "Cola 500ml", "units": 1, "extra": True},
        {"id": "inv_x", "store": "Store A", "product": "Cola 500ml"},
        {"id": "", "store": "Store A", "product": "Cola 500ml", "units": 1},
        {"id": "inv_x", "store": "Store A", "product": "Cola 500ml", "units": "48"},
        {"id": "inv_x", "store": "Store A", "product": "Cola 500ml", "units": -1},
        {"id": "inv_x", "store": "Store A", "product": "Cola 500ml", "units": 1.5},
    ],
)
def test_invalid_records_fail_safely(tmp_path: Path, payload: dict) -> None:
    path = _write(tmp_path, [payload])
    with pytest.raises(ValidationError):
        InventoryRepository(path)


def test_lookups_do_not_mutate_inventory() -> None:
    repo = InventoryRepository(INVENTORY_PATH)
    snapshot = [(record.id, record.store, record.product, record.units) for record in repo.all()]

    returned = repo.all()
    returned.clear()
    returned.append(
        InventoryRecord(id="inv_fake", store="Fake", product="Fake", units=99)
    )

    by_product = repo.find_by_product("Cola 500ml")
    by_product.clear()
    by_store = repo.find_by_store("Metro Fresh")
    by_store.pop()

    record = repo.get("inv_metro_fresh_cola_500ml")
    assert record is not None
    with pytest.raises(ValidationError):
        record.units = 99  # type: ignore[misc]

    assert [
        (item.id, item.store, item.product, item.units) for item in repo.all()
    ] == snapshot
    assert repo.find("Metro Fresh", "Cola 500ml").units == 48
    assert len(repo.find_by_product("Cola 500ml")) == 2
