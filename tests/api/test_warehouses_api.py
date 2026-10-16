from fastapi import status
from fastapi.testclient import TestClient


def test_create_warehouse_success(client: TestClient):
    payload = {
        "code": "WH-TEXAS-01",
        "name": "Dallas Hub",
        "location": "Dallas, TX",
        "is_active": True,
    }
    response = client.post("/api/v1/warehouses", json=payload)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["code"] == "WH-TEXAS-01"
    assert data["is_active"] is True
    assert "id" in data


def test_create_warehouse_duplicate_code(client: TestClient):
    payload = {
        "code": "WH-DUP-01",
        "name": "Original Warehouse",
    }
    res1 = client.post("/api/v1/warehouses", json=payload)
    assert res1.status_code == status.HTTP_201_CREATED

    res2 = client.post("/api/v1/warehouses", json=payload)
    assert res2.status_code == status.HTTP_409_CONFLICT
    assert res2.json()["error"]["code"] == "DUPLICATE_RESOURCE"


def test_update_warehouse_status(client: TestClient):
    wh_res = client.post(
        "/api/v1/warehouses",
        json={"code": "WH-TOGGLE-01", "name": "Toggle Warehouse"},
    )
    wh_id = wh_res.json()["id"]

    # Deactivate
    patch_res = client.patch(
        f"/api/v1/warehouses/{wh_id}/status",
        json={"is_active": False},
    )
    assert patch_res.status_code == status.HTTP_200_OK
    assert patch_res.json()["is_active"] is False
