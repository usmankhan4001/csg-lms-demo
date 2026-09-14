import datetime
from enum import Enum
from typing import Optional
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlmodel import Field, SQLModel


class ItemCategoryEnum(str, Enum):
    """Classification for school inventory items."""
    STATIONERY = "STATIONERY"
    UNIFORM = "UNIFORM"
    LAB_EQUIPMENT = "LAB_EQUIPMENT"
    SPORTS = "SPORTS"
    TEXTBOOK = "TEXTBOOK"
    FURNITURE = "FURNITURE"
    ELECTRONICS = "ELECTRONICS"
    MAINTENANCE = "MAINTENANCE"
    MEDICAL = "MEDICAL"
    OTHER = "OTHER"


class StockMovementTypeEnum(str, Enum):
    """Direction and intent of inventory stock movements."""
    IN = "IN"
    OUT = "OUT"
    ADJUSTMENT = "ADJUSTMENT"
    RETURN = "RETURN"
    PURCHASE = "PURCHASE"
    DISPOSAL = "DISPOSAL"


class PurchaseOrderStatusEnum(str, Enum):
    """Procurement purchase order lifecycle stages."""
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    ORDERED = "ORDERED"
    PARTIALLY_RECEIVED = "PARTIALLY_RECEIVED"
    FULFILLED = "FULFILLED"
    CANCELLED = "CANCELLED"


class Supplier(SQLModel, table=True):
    """
    Vendor or supplier record for institutional procurement.
    """
    __tablename__ = "sms_inventory_supplier"
    __table_args__ = (
        Index("ix_sms_supp_campus_name", "campus_id", "name"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    campus_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True, index=True))
    org_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True, index=True))
    name: str = Field(sa_column=Column(String(255), nullable=False, index=True))
    contact_person: Optional[str] = Field(default=None, sa_column=Column(String(150), nullable=True))
    email: Optional[str] = Field(default=None, sa_column=Column(String(150), nullable=True))
    phone: Optional[str] = Field(default=None, sa_column=Column(String(50), nullable=True))
    address: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    tax_id: Optional[str] = Field(default=None, sa_column=Column(String(100), nullable=True))
    payment_terms: Optional[str] = Field(default=None, sa_column=Column(String(100), nullable=True))
    is_active: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )
    updated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
            onupdate=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )


class InventoryItem(SQLModel, table=True):
    """
    Trackable inventory item (stationery, textbooks, uniforms, assets).
    """
    __tablename__ = "sms_inventory_item"
    __table_args__ = (
        Index("ix_sms_inv_campus_sku", "campus_id", "sku"),
        Index("ix_sms_inv_category", "category"),
        Index("ix_sms_inv_name", "name"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    campus_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True, index=True))
    org_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True, index=True))
    sku: str = Field(sa_column=Column(String(50), nullable=False, index=True))
    name: str = Field(sa_column=Column(String(255), nullable=False, index=True))
    category: ItemCategoryEnum = Field(
        default=ItemCategoryEnum.OTHER,
        sa_column=Column(
            SAEnum(ItemCategoryEnum, name="sms_inv_category", native_enum=False),
            nullable=False,
            default=ItemCategoryEnum.OTHER,
            index=True,
        ),
    )
    description: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    unit_of_measure: str = Field(
        default="pcs",
        sa_column=Column(String(50), nullable=False, default="pcs")
    )
    current_stock: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, default=0)
    )
    min_stock_threshold: int = Field(
        default=5,
        sa_column=Column(Integer, nullable=False, default=5)
    )
    unit_price: float = Field(
        default=0.0,
        sa_column=Column(Float, nullable=False, default=0.0)
    )
    location: Optional[str] = Field(default=None, sa_column=Column(String(100), nullable=True))
    is_active: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )
    updated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
            onupdate=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )


class StockMovement(SQLModel, table=True):
    """
    Immutable ledger audit trail of all inventory quantity adjustments.
    """
    __tablename__ = "sms_inventory_stock_movement"
    __table_args__ = (
        Index("ix_sms_stk_item_id", "item_id"),
        Index("ix_sms_stk_campus_id", "campus_id"),
        Index("ix_sms_stk_type", "movement_type"),
        Index("ix_sms_stk_created", "created_at"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    item_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sms_inventory_item.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    campus_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True, index=True))
    movement_type: StockMovementTypeEnum = Field(
        sa_column=Column(
            SAEnum(StockMovementTypeEnum, name="sms_stk_movement_type", native_enum=False),
            nullable=False,
            index=True,
        )
    )
    quantity: int = Field(sa_column=Column(Integer, nullable=False))
    previous_stock: int = Field(sa_column=Column(Integer, nullable=False))
    new_stock: int = Field(sa_column=Column(Integer, nullable=False))
    reference_type: Optional[str] = Field(default=None, sa_column=Column(String(50), nullable=True))
    reference_id: Optional[str] = Field(default=None, sa_column=Column(String(50), nullable=True))
    notes: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    performed_by_user_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )


class PurchaseOrder(SQLModel, table=True):
    """
    Institutional purchase order for supplier procurement.
    """
    __tablename__ = "sms_inventory_purchase_order"
    __table_args__ = (
        Index("ix_sms_po_number", "po_number"),
        Index("ix_sms_po_supplier", "supplier_id"),
        Index("ix_sms_po_campus", "campus_id"),
        Index("ix_sms_po_status", "status"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    po_number: str = Field(sa_column=Column(String(50), nullable=False, unique=True, index=True))
    supplier_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sms_inventory_supplier.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        )
    )
    campus_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True, index=True))
    status: PurchaseOrderStatusEnum = Field(
        default=PurchaseOrderStatusEnum.DRAFT,
        sa_column=Column(
            SAEnum(PurchaseOrderStatusEnum, name="sms_po_status", native_enum=False),
            nullable=False,
            default=PurchaseOrderStatusEnum.DRAFT,
            index=True,
        ),
    )
    order_date: datetime.date = Field(sa_column=Column(Date, nullable=False))
    expected_delivery_date: Optional[datetime.date] = Field(default=None, sa_column=Column(Date, nullable=True))
    delivery_date: Optional[datetime.date] = Field(default=None, sa_column=Column(Date, nullable=True))
    subtotal: float = Field(default=0.0, sa_column=Column(Float, nullable=False, default=0.0))
    tax: float = Field(default=0.0, sa_column=Column(Float, nullable=False, default=0.0))
    shipping_cost: float = Field(default=0.0, sa_column=Column(Float, nullable=False, default=0.0))
    total_amount: float = Field(default=0.0, sa_column=Column(Float, nullable=False, default=0.0))
    notes: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    created_by_user_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    approved_by_user_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    approved_at: Optional[datetime.datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )
    updated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
            onupdate=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )


class PurchaseOrderItem(SQLModel, table=True):
    """
    Line item for a purchase order.
    """
    __tablename__ = "sms_inventory_po_item"
    __table_args__ = (
        Index("ix_sms_poi_po_id", "po_id"),
        Index("ix_sms_poi_item_id", "item_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    po_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sms_inventory_purchase_order.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    item_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sms_inventory_item.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        )
    )
    quantity: int = Field(sa_column=Column(Integer, nullable=False))
    unit_price: float = Field(sa_column=Column(Float, nullable=False))
    received_quantity: int = Field(default=0, sa_column=Column(Integer, nullable=False, default=0))
    total_price: float = Field(sa_column=Column(Float, nullable=False))
