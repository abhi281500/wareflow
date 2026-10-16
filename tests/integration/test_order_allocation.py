from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.inventory import WarehouseInventory
from app.models.product import Product
from app.models.warehouse import Warehouse


def test_order_allocation_single_warehouse(
    client: TestClient, sample_product: Product, sample_warehouses: tuple[Warehouse, Warehouse]
):
    wh1, wh2 = sample_warehouses
    # Stock 100 in wh1, 10 in wh2
    client.post(
        "/api/v1/inventory/restock",
        json={"product_id": sample_product.id, "warehouse_id": wh1.id, "quantity": 100},
    )
    client.post(
        "/api/v1/inventory/restock",
        json={"product_id": sample_product.id, "warehouse_id": wh2.id, "quantity": 10},
    )

    # Order 30 units
    order_payload = {"items": [{"product_id": sample_product.id, "quantity": 30}]}
    response = client.post("/api/v1/orders", json=order_payload)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["status"] == "ALLOCATED"
    assert len(data["allocations"]) == 1
    assert data["allocations"][0]["warehouse_id"] == wh1.id
    assert data["allocations"][0]["quantity_allocated"] == 30

    # Verify inventory balances
    inv_res = client.get(f"/api/v1/inventory?product_id={sample_product.id}&warehouse_id={wh1.id}")
    inv_data = inv_res.json()[0]
    assert inv_data["quantity_available"] == 70
    assert inv_data["quantity_reserved"] == 30


def test_order_split_allocation(
    client: TestClient, sample_product: Product, sample_warehouses: tuple[Warehouse, Warehouse]
):
    wh1, wh2 = sample_warehouses
    # Stock 20 in wh1, 20 in wh2
    client.post(
        "/api/v1/inventory/restock",
        json={"product_id": sample_product.id, "warehouse_id": wh1.id, "quantity": 20},
    )
    client.post(
        "/api/v1/inventory/restock",
        json={"product_id": sample_product.id, "warehouse_id": wh2.id, "quantity": 20},
    )

    # Request 35 units (requires splitting across both warehouses)
    order_payload = {"items": [{"product_id": sample_product.id, "quantity": 35}]}
    response = client.post("/api/v1/orders", json=order_payload)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["status"] == "ALLOCATED"
    assert len(data["allocations"]) == 2
    total_allocated = sum(a["quantity_allocated"] for a in data["allocations"])
    assert total_allocated == 35


def test_order_insufficient_stock_rollback(
    client: TestClient,
    db: Session,
    sample_product: Product,
    sample_warehouses: tuple[Warehouse, Warehouse],
):
    wh1, _ = sample_warehouses
    client.post(
        "/api/v1/inventory/restock",
        json={"product_id": sample_product.id, "warehouse_id": wh1.id, "quantity": 10},
    )

    # Request 50 units (only 10 available)
    order_payload = {"items": [{"product_id": sample_product.id, "quantity": 50}]}
    response = client.post("/api/v1/orders", json=order_payload)
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["error"]["code"] == "INSUFFICIENT_STOCK"

    # Transaction safety verification: Available stock MUST still be 10, NOT partially deducted
    inv = db.scalar(
        select(WarehouseInventory).where(
            WarehouseInventory.product_id == sample_product.id,
            WarehouseInventory.warehouse_id == wh1.id,
        )
    )
    assert inv.quantity_available == 10
    assert inv.quantity_reserved == 0


def test_order_cancellation_releases_stock_once(
    client: TestClient, sample_product: Product, sample_warehouses: tuple[Warehouse, Warehouse]
):
    wh1, _ = sample_warehouses
    client.post(
        "/api/v1/inventory/restock",
        json={"product_id": sample_product.id, "warehouse_id": wh1.id, "quantity": 50},
    )

    # Create order for 20
    res = client.post("/api/v1/orders", json={"items": [{"product_id": sample_product.id, "quantity": 20}]})
    order_id = res.json()["id"]

    # Cancel order
    cancel_res = client.post(f"/api/v1/orders/{order_id}/cancel")
    assert cancel_res.status_code == status.HTTP_200_OK
    assert cancel_res.json()["status"] == "CANCELLED"

    # Verify inventory is restored
    inv_res = client.get(f"/api/v1/inventory?product_id={sample_product.id}&warehouse_id={wh1.id}")
    inv_data = inv_res.json()[0]
    assert inv_data["quantity_available"] == 50
    assert inv_data["quantity_reserved"] == 0

    # Repeat cancellation must be rejected and must not double-release stock
    repeat_res = client.post(f"/api/v1/orders/{order_id}/cancel")
    assert repeat_res.status_code == status.HTTP_400_BAD_REQUEST
    assert repeat_res.json()["error"]["code"] == "INVALID_ORDER_STATE"

    # Stock must remain unchanged
    inv_res2 = client.get(f"/api/v1/inventory?product_id={sample_product.id}&warehouse_id={wh1.id}")
    assert inv_res2.json()[0]["quantity_available"] == 50
