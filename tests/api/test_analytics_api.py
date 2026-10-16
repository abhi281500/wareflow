from fastapi import status
from fastapi.testclient import TestClient

from app.models.product import Product
from app.models.warehouse import Warehouse


def test_analytics_summary_and_alerts(
    client: TestClient, sample_product: Product, sample_warehouses: tuple[Warehouse, Warehouse]
):
    wh1, wh2 = sample_warehouses
    # Restock 5 in wh1 (below alert threshold of 10)
    client.post(
        "/api/v1/inventory/restock",
        json={"product_id": sample_product.id, "warehouse_id": wh1.id, "quantity": 5},
    )

    # Summary
    summary_res = client.get("/api/v1/analytics/summary")
    assert summary_res.status_code == status.HTTP_200_OK
    summary = summary_res.json()
    assert summary["total_products"] >= 1
    assert summary["total_warehouses"] >= 2
    assert summary["total_available_stock"] == 5

    # Warehouse Stock
    wh_stock_res = client.get("/api/v1/analytics/warehouse-stock")
    assert wh_stock_res.status_code == status.HTTP_200_OK
    wh_stock = wh_stock_res.json()
    assert len(wh_stock) >= 2

    # Reorder alerts
    alerts_res = client.get("/api/v1/analytics/reorder-alerts?threshold=10")
    assert alerts_res.status_code == status.HTTP_200_OK
    alerts = alerts_res.json()
    assert len(alerts) == 1
    assert alerts[0]["product_id"] == sample_product.id
    assert alerts[0]["quantity_available"] == 5

    # Order Status counts
    order_counts_res = client.get("/api/v1/analytics/order-status-counts")
    assert order_counts_res.status_code == status.HTTP_200_OK
    counts = order_counts_res.json()
    assert "allocated" in counts
    assert "cancelled" in counts
    assert "total_orders" in counts
