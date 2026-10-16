from fastapi import status
from fastapi.testclient import TestClient


def test_create_product_success(client: TestClient):
    payload = {
        "sku": "PROD-KEYBOARD-01",
        "name": "Mechanical Keyboard",
        "description": "RGB Backlit keyboard",
        "price": 89.99,
    }
    response = client.post("/api/v1/products", json=payload)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["sku"] == "PROD-KEYBOARD-01"
    assert data["name"] == "Mechanical Keyboard"
    assert float(data["price"]) == 89.99
    assert "id" in data


def test_create_product_duplicate_sku_fails(client: TestClient):
    payload = {
        "sku": "PROD-DUPLICATE-01",
        "name": "First Instance",
        "price": 45.00,
    }
    res1 = client.post("/api/v1/products", json=payload)
    assert res1.status_code == status.HTTP_201_CREATED

    res2 = client.post("/api/v1/products", json=payload)
    assert res2.status_code == status.HTTP_409_CONFLICT
    assert res2.json()["error"]["code"] == "DUPLICATE_RESOURCE"


def test_create_product_invalid_price(client: TestClient):
    payload = {
        "sku": "PROD-INVALID-PRICE",
        "name": "Free Item",
        "price": -10.00,
    }
    response = client.post("/api/v1/products", json=payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_get_product_not_found(client: TestClient):
    response = client.get("/api/v1/products/999999")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
