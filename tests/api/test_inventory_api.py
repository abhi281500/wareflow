from fastapi import status
from fastapi.testclient import TestClient

from app.models.product import Product
from app.models.warehouse import Warehouse


def test_restock_success(client: TestClient, sample_product: Product, sample_warehouses: tuple[Warehouse, Warehouse]):
    wh1, _ = sample_warehouses
    payload = {
        "product_id": sample_product.id,
        "warehouse_id": wh1.id,
        "quantity": 50,
    }
    response = client.post("/api/v1/inventory/restock", json=payload)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["quantity_available"] == 50
    assert data["quantity_reserved"] == 0

    # Restock again to verify accumulation
    response2 = client.post(
        "/api/v1/inventory/restock",
        json={"product_id": sample_product.id, "warehouse_id": wh1.id, "quantity": 25},
    )
    assert response2.status_code == status.HTTP_200_OK
    assert response2.json()["quantity_available"] == 75


def test_restock_inactive_warehouse_fails(
    client: TestClient, sample_product: Product, sample_warehouses: tuple[Warehouse, Warehouse]
):
    wh1, _ = sample_warehouses
    # Deactivate warehouse
    client.patch(f"/api/v1/warehouses/{wh1.id}/status", json={"is_active": False})

    payload = {
        "product_id": sample_product.id,
        "warehouse_id": wh1.id,
        "quantity": 10,
    }
    response = client.post("/api/v1/inventory/restock", json=payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert response.json()["error"]["code"] == "INACTIVE_WAREHOUSE"


def test_restock_negative_quantity_fails(
    client: TestClient, sample_product: Product, sample_warehouses: tuple[Warehouse, Warehouse]
):
    wh1, _ = sample_warehouses
    payload = {
        "product_id": sample_product.id,
        "warehouse_id": wh1.id,
        "quantity": -5,
    }
    response = client.post("/api/v1/inventory/restock", json=payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
