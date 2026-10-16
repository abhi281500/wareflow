from collections.abc import Generator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.product import Product
from app.models.warehouse import Warehouse

# PostgreSQL test database engine
test_engine = create_engine(
    settings.TEST_DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

TestingSessionLocal = sessionmaker(
    bind=test_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Drops and re-creates all tables in wareflow_test before running tests."""
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(autouse=True)
def clean_tables_after_test():
    """Ensures a clean slate for each test by deleting table data between tests."""
    yield
    with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture
def db() -> Generator[Session]:
    """Provides a dedicated database session for test assertions."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client() -> Generator[TestClient]:
    """FastAPI test client with get_db overridden to use TestingSessionLocal."""

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_product(db: Session) -> Product:
    product = Product(
        sku="TEST-SKU-001",
        name="Test Laptop",
        description="High-performance laptop",
        price=Decimal("1200.00"),
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@pytest.fixture
def sample_warehouses(db: Session) -> tuple[Warehouse, Warehouse]:
    wh1 = Warehouse(code="WH-EAST-01", name="East Warehouse", location="New York", is_active=True)
    wh2 = Warehouse(code="WH-WEST-01", name="West Warehouse", location="California", is_active=True)
    db.add_all([wh1, wh2])
    db.commit()
    db.refresh(wh1)
    db.refresh(wh2)
    return wh1, wh2
