# WareFlow — Multi-Warehouse Inventory Allocation & Concurrency Control Service

![Python](https://img.shields.io/badge/Python-3.13+-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-18-4169E1?style=flat&logo=postgresql&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0+-D71F00?style=flat&logo=sqlalchemy&logoColor=white)
![Pydantic](https://img.shields.io/badge/Pydantic-v2-E92063?style=flat&logo=pydantic&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat&logo=docker&logoColor=white)
![Ruff](https://img.shields.io/badge/Ruff-Formatted-D7FF64?style=flat&logo=ruff&logoColor=black)

**WareFlow** is a production-minded Python backend service designed to solve high-concurrency inventory allocation across distributed warehouses. It prevents overselling, lost updates, and race conditions through **deterministic pessimistic row-level locking (`SELECT ... FOR UPDATE`)**, atomic transaction boundaries, strict database invariants, and idempotency key persistence.

---

## 1. Problem Statement & Real-World Context

In distributed e-commerce logistics, products are stored across multiple fulfillment centers. When flash sales occur or multiple customers place orders simultaneously for the same stock:
1. **The Overselling / Race Condition Risk:** If two requests read available stock at the same millisecond and issue uncoordinated updates, inventory balances can drop below zero, leaving retailers unable to fulfill orders.
2. **The Deadlock Risk:** If Order A reserves Product 1 then Product 2, while Order B concurrently reserves Product 2 then Product 1, the database aborts one transaction due to circular wait locks.
3. **The Duplicate Payment / Retry Risk:** Network dropouts cause client retries; without cryptographic idempotency enforcement, stock can be deducted multiple times for the same purchase.

WareFlow resolves all three challenges in the **database transaction engine itself**, rather than relying solely on naive application-level checks.

---

## 2. Architecture & Design Principles

```mermaid
flowchart TD
    Client["Client / Concurrent Checkout Workers"] -->|HTTP / JSON + Idempotency-Key| API["FastAPI Route Handlers (app/api/v1)"]
    API -->|Validates via Pydantic Schemas| Schemas["Pydantic v2 Models (app/schemas)"]
    API -->|Injects DB Session & Calls| Services["Service Layer (app/services)"]
    
    subgraph Core Business Services
        IdempServ["IdempotencyService"]
        AllocServ["OrderAllocationService"]
        InvServ["InventoryService"]
    end
    
    Services --> IdempServ
    Services --> AllocServ
    Services --> InvServ

    AllocServ -->|Acquires Row Locks in Sorted Order| ORM["SQLAlchemy 2.x ORM / Repositories"]
    ORM -->|BEGIN TRANSACTION ... SELECT FOR UPDATE| DB[("PostgreSQL 18 Database")]

    subgraph PostgreSQL Database Engine
        Constraints["CHECK (quantity_available >= 0)\nUNIQUE (product_id, warehouse_id)"]
        RowLocks["Pessimistic Row Locks (FOR UPDATE)"]
        Tables["Products | Warehouses | Inventory | Orders | Allocations | Idempotency"]
    end

    DB --> Constraints
    DB --> RowLocks
    DB --> Tables
```

### Architectural Highlights:
- **Clean Layered Separation:** API routes (`app/api/`), Pydantic validation schemas (`app/schemas/`), Domain business services (`app/services/`), SQLAlchemy 2.0 ORM mapped models (`app/models/`), and database migration engine (`alembic/`).
- **Synchronous SQLAlchemy 2.x with Psycopg 3:** Keeps transaction lifecycles, lock acquisitions, and isolation semantics clear, deterministic, and interview-defensible.
- **Strict Stock Invariants:**
  - $\text{quantity\_available} \ge 0$ (enforced by PostgreSQL `CHECK` constraint).
  - $\text{quantity\_reserved} \ge 0$ (enforced by PostgreSQL `CHECK` constraint).
  - Unique product-warehouse inventory pairing (`UNIQUE(product_id, warehouse_id)`).

---

## 3. Concurrency & Idempotency Strategy

### Deterministic Lock Ordering (Deadlock Elimination)
To prevent circular wait locks when concurrent orders touch overlapping products:
```sql
SELECT * FROM warehouse_inventory 
WHERE product_id IN (...) AND warehouse_id IN (...)
ORDER BY product_id ASC, warehouse_id ASC
FOR UPDATE;
```
Because every transaction locks inventory rows in the **exact same ascending sequence** (`product_id ASC, warehouse_id ASC`), deadlocks are mathematically prevented.

### Multi-Warehouse Allocation Rules
1. **Single Warehouse Optimization:** If an active warehouse has sufficient inventory for all items in the order, fulfill entirely from that single facility to minimize shipping costs and split packages.
2. **Split Allocation Fallback:** If no single facility has enough stock, the service splits the items across active warehouses, prioritizing facilities with the highest available inventory.
3. **All-or-Nothing Rollback:** If any item cannot be completely fulfilled across all active warehouses, an `InsufficientStockException` is raised, triggering an atomic `ROLLBACK`. Zero partial deductions remain.

### Safe Cancellation
When an allocated order is cancelled:
- The order row and associated inventory rows are locked with `FOR UPDATE`.
- Reserved quantities are decremented and returned to available stock.
- The order status transitions to `CANCELLED`.
- A second cancellation attempt is rejected with HTTP `400 Bad Request` (`INVALID_ORDER_STATE`), guaranteeing stock is **never restored twice**.

### Idempotency Key Engine
- Clients send an `Idempotency-Key` header with order requests.
- The service computes a canonical SHA-256 hash of the request payload.
- If the key is seen again with the identical payload, the cached response is replayed without re-executing order creation or stock deductions.
- If the key is reused with a *different* payload, HTTP `409 Conflict` (`IDEMPOTENCY_CONFLICT`) is returned.

---

## 4. Setup & Running Locally

### Prerequisites
- Python 3.12+ (tested with Python 3.13)
- PostgreSQL (or Docker)

### 1. Clone & Setup Virtual Environment
```powershell
# Clone the repository
git clone https://github.com/your-username/wareflow.git
cd wareflow

# Create and activate virtual environment
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install Dependencies
```powershell
pip install -r requirements-dev.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env`:
```powershell
Copy-Item .env.example .env
```
Ensure `DATABASE_URL` and `TEST_DATABASE_URL` match your PostgreSQL credentials:
```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/wareflow_dev
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/wareflow_test
```

### 4. Run Migrations & Start Server
```powershell
# Apply database migrations
alembic upgrade head

# Launch development server
uvicorn app.main:app --reload --port 8000
```
API Documentation will be available at `http://localhost:8000/docs`.

---

## 5. Docker Deployment

To run WareFlow in isolated containers with a dedicated PostgreSQL database:

```powershell
# Build and start services
docker compose up -d --build

# Run migrations inside the container
docker compose exec app alembic upgrade head

# Check logs
docker compose logs -f app
```

To stop and remove containers:
```powershell
docker compose down
```

---

## 6. Automated Testing & Verification

WareFlow features a complete automated test suite covering unit logic, API contracts, PostgreSQL rollback transactions, and multi-threaded race conditions:

```powershell
# Run the complete test suite
pytest -v
```

### Verified Test Suite Breakdown (21 Tests):
- `tests/api/test_products_api.py`: Product creation, duplicate SKU rejection, price validation, 404 handling.
- `tests/api/test_warehouses_api.py`: Warehouse creation, unique code verification, status toggling.
- `tests/api/test_inventory_api.py`: Restocking, inactive warehouse validation, negative quantity rejection.
- `tests/api/test_analytics_api.py`: Summary metrics, warehouse aggregation, low-stock reorder alerts.
- `tests/integration/test_order_allocation.py`: Single-warehouse fulfillment, split allocation, insufficient stock rollback.
- `tests/integration/test_idempotency.py`: Replay safety, payload mismatch rejection.
- `tests/concurrency/test_concurrent_allocation.py`: **15 concurrent worker threads** competing for 10 units of stock. Demonstrates zero overselling and exact stock invariant maintenance.
- `tests/unit/test_business_rules.py`: Deterministic hash invariance across key orderings, exception hierarchy.

### Code Style & Linting
```powershell
ruff check .
ruff format --check .
```

---

## 7. API Reference & Sample Requests

### 1. Create a Product
```bash
curl -X POST http://localhost:8000/api/v1/products \
  -H "Content-Type: application/json" \
  -d '{
    "sku": "PROD-MACBOOK-M3",
    "name": "Apple MacBook Pro M3",
    "description": "16-inch, 36GB RAM, 512GB SSD",
    "price": 2499.00
  }'
```

### 2. Create Warehouses
```bash
curl -X POST http://localhost:8000/api/v1/warehouses \
  -H "Content-Type: application/json" \
  -d '{
    "code": "WH-SEATTLE-01",
    "name": "Seattle Fulfillment Center",
    "location": "Seattle, WA",
    "is_active": true
  }'
```

### 3. Restock Inventory
```bash
curl -X POST http://localhost:8000/api/v1/inventory/restock \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": 1,
    "warehouse_id": 1,
    "quantity": 100
  }'
```

### 4. Create Order (with Idempotency Key)
```bash
curl -X POST http://localhost:8000/api/v1/orders \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: e8b9f71c-4b68-450a-99ef-8676a0862089" \
  -d '{
    "order_number": "ORD-2026-0001",
    "items": [
      {
        "product_id": 1,
        "quantity": 2
      }
    ]
  }'
```

### 5. Cancel Order
```bash
curl -X POST http://localhost:8000/api/v1/orders/1/cancel
```

### 6. View Reorder Alerts
```bash
curl http://localhost:8000/api/v1/analytics/reorder-alerts?threshold=10
```

---

## 8. Technical Interview Preparation (Placement Q&A)

As part of technical placement interview readiness, here are 5 key architectural questions based directly on this project:

#### Q1: Why did you use `SELECT ... FOR UPDATE` instead of Optimistic Concurrency Control (OCC)?
> **Answer:** In high-contention e-commerce flash sales, Optimistic Concurrency Control (version columns) suffers from high rollback and retry rates because multiple clients attempt to write to the same row simultaneously. Pessimistic row locking (`SELECT FOR UPDATE`) serializes the access at the database level, ensuring requests queue and proceed without wasted application-level retry loops.

#### Q2: How did you prevent deadlocks during multi-item order allocation?
> **Answer:** Deadlocks occur when transactions acquire locks in circular order (e.g., Tx1 locks item A then wants B, while Tx2 locks item B then wants A). WareFlow eliminates deadlocks by enforcing **deterministic lock sorting**: all inventory rows are sorted strictly by `(product_id ASC, warehouse_id ASC)` before executing the locking query.

#### Q3: Why can't you apply `FOR UPDATE` to an outer join in PostgreSQL?
> **Answer:** PostgreSQL explicitly disallows `FOR UPDATE` on the nullable side of an outer join (`psycopg.errors.FeatureNotSupported`). If an outer row is null (no match), locking it is conceptually undefined. In WareFlow, we lock the primary `orders` table first, and query related order items and allocations through dedicated queries.

#### Q4: How does your idempotency mechanism handle concurrent requests with the same key?
> **Answer:** When a request arrives, it inserts or acquires an `IdempotencyRecord` with status `PROCESSING`. If a concurrent request arrives with the same key while status is `PROCESSING`, it is immediately rejected with HTTP `409 Conflict`. Once the initial transaction commits, the record is updated to `COMPLETED` with the response body.

#### Q5: What database constraints protect inventory if application logic fails?
> **Answer:** WareFlow uses PostgreSQL `CHECK` constraints (`quantity_available >= 0` and `quantity_reserved >= 0`) and a `UNIQUE(product_id, warehouse_id)` constraint. Even if an application bug bypassed validation, PostgreSQL raises an `IntegrityError`, aborting the transaction before invalid state is persisted.
