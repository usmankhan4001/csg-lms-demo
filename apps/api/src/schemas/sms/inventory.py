import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from src.db.sms_inventory import (
    ItemCategoryEnum,
    PurchaseOrderStatusEnum,
    StockMovementTypeEnum,
)


# ── Inventory Item Schemas ──

class InventoryItemCreate(BaseModel):
    campus_id: Optional[int] = Field(None, description="Campus ID where stock is maintained")
    org_id: Optional[int] = Field(None, description="Organization ID")
    sku: str = Field(..., min_length=1, max_length=50, description="SKU / Item code")
    name: str = Field(..., min_length=1, max_length=255, description="Item name")
    category: ItemCategoryEnum = Field(default=ItemCategoryEnum.OTHER, description="Item category")
    description: Optional[str] = Field(None, description="Detailed description")
    unit_of_measure: str = Field(default="pcs", max_length=50, description="Unit e.g. pcs, boxes, kg")
    current_stock: int = Field(default=0, ge=0, description="Initial stock quantity")
    min_stock_threshold: int = Field(default=5, ge=0, description="Threshold below which alert triggers")
    unit_price: float = Field(default=0.0, ge=0.0, description="Standard purchase or unit price")
    location: Optional[str] = Field(None, max_length=100, description="Warehouse or room location")


class InventoryItemUpdate(BaseModel):
    sku: Optional[str] = Field(None, min_length=1, max_length=50)
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    category: Optional[ItemCategoryEnum] = None
    description: Optional[str] = None
    unit_of_measure: Optional[str] = Field(None, max_length=50)
    min_stock_threshold: Optional[int] = Field(None, ge=0)
    unit_price: Optional[float] = Field(None, ge=0.0)
    location: Optional[str] = None
    is_active: Optional[bool] = None


class InventoryItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: Optional[int] = None
    org_id: Optional[int] = None
    sku: str
    name: str
    category: ItemCategoryEnum
    description: Optional[str] = None
    unit_of_measure: str
    current_stock: int
    min_stock_threshold: int
    unit_price: float
    location: Optional[str] = None
    is_active: bool
    is_low_stock: bool = False
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ── Stock Movement Schemas ──

class StockAdjustmentCreate(BaseModel):
    movement_type: StockMovementTypeEnum = Field(..., description="IN, OUT, ADJUSTMENT, RETURN, DISPOSAL")
    quantity: int = Field(..., description="Quantity delta (positive integer; direction inferred by type or delta)")
    reference_type: Optional[str] = Field(None, description="e.g. MANUAL_ADJUSTMENT, AUDIT, RETURN")
    reference_id: Optional[str] = Field(None, description="External reference ID")
    notes: Optional[str] = Field(None, description="Reason for adjustment")


class StockMovementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int
    campus_id: Optional[int] = None
    movement_type: StockMovementTypeEnum
    quantity: int
    previous_stock: int
    new_stock: int
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None
    notes: Optional[str] = None
    performed_by_user_id: Optional[int] = None
    created_at: datetime.datetime


# ── Supplier Schemas ──

class SupplierCreate(BaseModel):
    campus_id: Optional[int] = Field(None, description="Campus ID")
    org_id: Optional[int] = Field(None, description="Organization ID")
    name: str = Field(..., min_length=1, max_length=255, description="Supplier company name")
    contact_person: Optional[str] = Field(None, max_length=150)
    email: Optional[str] = Field(None, max_length=150)
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = None
    tax_id: Optional[str] = Field(None, max_length=100)
    payment_terms: Optional[str] = Field(None, max_length=100)


class SupplierUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    contact_person: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    tax_id: Optional[str] = None
    payment_terms: Optional[str] = None
    is_active: Optional[bool] = None


class SupplierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: Optional[int] = None
    org_id: Optional[int] = None
    name: str
    contact_person: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    tax_id: Optional[str] = None
    payment_terms: Optional[str] = None
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ── Purchase Order Line Items ──

class PurchaseOrderItemCreate(BaseModel):
    item_id: int = Field(..., description="Inventory item ID")
    quantity: int = Field(..., gt=0, description="Quantity to order")
    unit_price: float = Field(..., ge=0.0, description="Negotiated unit price")


class PurchaseOrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    po_id: int
    item_id: int
    item_name: Optional[str] = None
    item_sku: Optional[str] = None
    quantity: int
    unit_price: float
    received_quantity: int
    total_price: float


# ── Purchase Order Schemas ──

class PurchaseOrderCreate(BaseModel):
    supplier_id: int = Field(..., description="Supplier ID")
    campus_id: Optional[int] = Field(None, description="Campus ID")
    order_date: datetime.date = Field(default_factory=datetime.date.today)
    expected_delivery_date: Optional[datetime.date] = None
    tax: float = Field(default=0.0, ge=0.0)
    shipping_cost: float = Field(default=0.0, ge=0.0)
    notes: Optional[str] = None
    items: List[PurchaseOrderItemCreate] = Field(..., min_length=1, description="Line items")


class PurchaseOrderUpdate(BaseModel):
    expected_delivery_date: Optional[datetime.date] = None
    tax: Optional[float] = Field(None, ge=0.0)
    shipping_cost: Optional[float] = Field(None, ge=0.0)
    notes: Optional[str] = None


class PurchaseOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    po_number: str
    supplier_id: int
    supplier_name: Optional[str] = None
    campus_id: Optional[int] = None
    status: PurchaseOrderStatusEnum
    order_date: datetime.date
    expected_delivery_date: Optional[datetime.date] = None
    delivery_date: Optional[datetime.date] = None
    subtotal: float
    tax: float
    shipping_cost: float
    total_amount: float
    notes: Optional[str] = None
    created_by_user_id: Optional[int] = None
    approved_by_user_id: Optional[int] = None
    approved_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class PurchaseOrderDetailRead(PurchaseOrderRead):
    items: List[PurchaseOrderItemRead] = []


class ReceiveItemPayload(BaseModel):
    item_id: int = Field(..., description="Item ID being received")
    quantity_received: int = Field(..., gt=0, description="Quantity received in this batch")


class ReceivePurchaseOrderRequest(BaseModel):
    items: List[ReceiveItemPayload] = Field(..., min_length=1, description="Items received")
    notes: Optional[str] = Field(None, description="Receiving notes or condition inspection")


# ── Dashboard & Analytics Schemas ──

class LowStockAlertRead(BaseModel):
    item_id: int
    sku: str
    name: str
    category: ItemCategoryEnum
    current_stock: int
    min_stock_threshold: int
    unit_of_measure: str
    deficit: int
    location: Optional[str] = None


class InventorySummaryRead(BaseModel):
    total_items: int
    total_stock_units: int
    total_inventory_value: float
    low_stock_count: int
    pending_po_count: int
    total_suppliers: int
