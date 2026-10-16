import uuid

from fastapi import status
from fastapi.testclient import TestClient

from app.models.product import Product
from app.models.warehouse import Warehouse


def test_idempotent_order_creation_retries_safely(
    client: TestClient, sample_product: Product, sample_warehouses: tuple[Warehouse, Warehouse]
):
    wh1, _ = sample_warehouses
    client.post(
        "/api/v1/inventory/restock",
        json={"product_id": sample_product.id, "warehouse_id": wh1.id, "quantity": 100},
    )

    idempotency_key = f"IDEMP-{uuid.uuid4().hex}"
    payload = {"items": [{"product_id": sample_product.id, "quantity": 15}]}

    # First request
    res1 = client.post("/api/v1/orders", json=payload, headers={"Idempotency-Key": idempotency_key})
    assert res1.status_code == status.HTTP_201_CREATED
    data1 = res1.json()

    # Second request with SAME key and SAME payload (network retry scenario)
    res2 = client.post("/api/v1/orders", json=payload, headers={"Idempotency-Key": idempotency_key})
    assert res2.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED)
    data2 = res2.json()

    # Must return identical order id and order number
    assert data1["id"] == data2["id"]
    assert data1["order_number"] == data2["order_number"]

    # Verify inventory was deducted ONCE (100 - 15 = 85 available), not twice!
    inv_res = client.get(f"/api/v1/inventory?product_id={sample_product.id}&warehouse_id={wh1.id}")
    assert inv_res.json()[0]["quantity_available"] == 85


def test_idempotent_key_reuse_with_different_payload_fails(
    client: TestClient, sample_product: Product, sample_warehouses: tuple[Warehouse, Warehouse]
):
    wh1, _ = sample_warehouses
    client.post(
        "/api/v1/inventory/restock",
        json={"product_id": sample_product.id, "warehouse_id": wh1.id, "quantity": 100},
    )

    idempotency_key = f"IDEMP-CONFLICT-{uuid.uuid4().hex}"
    payload1 = {"items": [{"product_id": sample_product.id, "quantity": 10}]}
    payload2 = {"items": [{"product_id": sample_product.id, "quantity": 20}]}

    # First request succeeds
    res1 = client.post("/api/v1/orders", json=payload1, headers={"Idempotency-Key": idempotency_key})
    assert res1.status_code == status.HTTP_201_CREATED

    # Second request with SAME key but DIFFERENT payload must fail with 409 Conflict
    res2 = client.post("/api/v1/orders", json=payload2, headers={"Idempotency-Key": idempotency_key})
    assert res2.status_code == status.HTTP_409_CONFLICT
    assert res2.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
