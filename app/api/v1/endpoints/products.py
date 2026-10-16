from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import DuplicateResourceException, ResourceNotFoundException
from app.db.session import get_db
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductResponse

router = APIRouter(prefix="/products", tags=["Products"])


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(product_in: ProductCreate, db: Session = Depends(get_db)):
    """Creates a new product with a unique SKU."""
    existing = db.scalar(select(Product).where(Product.sku == product_in.sku))
    if existing:
        raise DuplicateResourceException(f"Product with SKU '{product_in.sku}' already exists")

    product = Product(
        sku=product_in.sku,
        name=product_in.name,
        description=product_in.description,
        price=product_in.price,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.get("", response_model=list[ProductResponse])
def list_products(
    sku: str | None = Query(None, description="Filter by SKU substring"),
    name: str | None = Query(None, description="Filter by product name substring"),
    db: Session = Depends(get_db),
):
    """Lists products with optional filtering."""
    stmt = select(Product)
    if sku:
        stmt = stmt.where(Product.sku.ilike(f"%{sku}%"))
    if name:
        stmt = stmt.where(Product.name.ilike(f"%{name}%"))
    return list(db.scalars(stmt).all())


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(product_id: int, db: Session = Depends(get_db)):
    """Retrieves a single product by ID."""
    product = db.get(Product, product_id)
    if not product:
        raise ResourceNotFoundException(f"Product with ID {product_id} not found")
    return product
