import datetime
import uuid
from typing import List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_inventory import (
    InventoryItem,
    ItemCategoryEnum,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseOrderStatusEnum,
    StockMovement,
    StockMovementTypeEnum,
    Supplier,
)
from src.schemas.sms.inventory import (
    InventoryItemCreate,
    InventoryItemRead,
    InventoryItemUpdate,
    InventorySummaryRead,
    LowStockAlertRead,
    PurchaseOrderCreate,
    PurchaseOrderRead,
    PurchaseOrderUpdate,
    ReceivePurchaseOrderRequest,
    StockAdjustmentCreate,
    SupplierCreate,
    SupplierRead,
    SupplierUpdate,
)


# ── Inventory Items ──

async def create_inventory_item(
    session: AsyncSession,
    payload: InventoryItemCreate,
    campus_id: Optional[int] = None,
    org_id: Optional[int] = None,
) -> InventoryItem:
    # Check SKU uniqueness per campus/org
    query = select(InventoryItem).where(InventoryItem.sku == payload.sku)
    if campus_id is not None:
        query = query.where(InventoryItem.campus_id == campus_id)
    existing = (await session.exec(query)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"An item with SKU '{payload.sku}' already exists in this campus.",
        )

    resolved_campus_id = payload.campus_id if payload.campus_id is not None else campus_id
    resolved_org_id = payload.org_id if payload.org_id is not None else org_id

    item = InventoryItem(
        campus_id=resolved_campus_id,
        org_id=resolved_org_id,
        sku=payload.sku.strip(),
        name=payload.name.strip(),
        category=payload.category,
        description=payload.description,
        unit_of_measure=payload.unit_of_measure,
        current_stock=payload.current_stock,
        min_stock_threshold=payload.min_stock_threshold,
        unit_price=payload.unit_price,
        location=payload.location,
        is_active=True,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)

    # If initial stock > 0, log initial stock movement
    if payload.current_stock > 0:
        movement = StockMovement(
            item_id=item.id,
            campus_id=resolved_campus_id,
            movement_type=StockMovementTypeEnum.IN,
            quantity=payload.current_stock,
            previous_stock=0,
            new_stock=payload.current_stock,
            reference_type="INITIAL_COUNT",
            notes="Initial stock upon item creation",
        )
        session.add(movement)
        await session.commit()

    return item


async def update_inventory_item(
    session: AsyncSession,
    item_id: int,
    payload: InventoryItemUpdate,
) -> InventoryItem:
    item = await session.get(InventoryItem, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory item not found.")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(item, key, value)

    item.updated_at = datetime.datetime.now(datetime.timezone.utc)
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


async def delete_inventory_item(session: AsyncSession, item_id: int) -> None:
    item = await session.get(InventoryItem, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory item not found.")
    await session.delete(item)
    await session.commit()


async def get_inventory_item(session: AsyncSession, item_id: int) -> InventoryItem:
    item = await session.get(InventoryItem, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory item not found.")
    return item


async def list_inventory_items(
    session: AsyncSession,
    campus_id: Optional[int] = None,
    category: Optional[ItemCategoryEnum] = None,
    low_stock_only: bool = False,
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[InventoryItem]:
    query = select(InventoryItem)
    if campus_id is not None:
        query = query.where(InventoryItem.campus_id == campus_id)
    if category is not None:
        query = query.where(InventoryItem.category == category)
    if is_active is not None:
        query = query.where(InventoryItem.is_active == is_active)
    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            or_(
                InventoryItem.name.ilike(search_pattern),
                InventoryItem.sku.ilike(search_pattern),
                InventoryItem.location.ilike(search_pattern),
            )
        )
    if low_stock_only:
        query = query.where(InventoryItem.current_stock <= InventoryItem.min_stock_threshold)

    query = query.order_by(InventoryItem.name).offset(offset).limit(limit)
    result = await session.exec(query)
    return result.all()


# ── Stock Adjustments & Tracking ──

async def adjust_stock(
    session: AsyncSession,
    item_id: int,
    payload: StockAdjustmentCreate,
    performed_by_user_id: Optional[int] = None,
    campus_id: Optional[int] = None,
) -> Tuple[InventoryItem, StockMovement]:
    item = await session.get(InventoryItem, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory item not found.")

    previous_stock = item.current_stock
    qty = payload.quantity

    if payload.movement_type in [StockMovementTypeEnum.IN, StockMovementTypeEnum.PURCHASE, StockMovementTypeEnum.RETURN]:
        delta = abs(qty)
    elif payload.movement_type in [StockMovementTypeEnum.OUT, StockMovementTypeEnum.DISPOSAL]:
        delta = -abs(qty)
    elif payload.movement_type == StockMovementTypeEnum.ADJUSTMENT:
        delta = qty
    else:
        delta = qty

    new_stock = previous_stock + delta
    if new_stock < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Adjustment results in negative stock ({new_stock}). Available stock: {previous_stock}.",
        )

    item.current_stock = new_stock
    item.updated_at = datetime.datetime.now(datetime.timezone.utc)
    session.add(item)

    movement = StockMovement(
        item_id=item.id,
        campus_id=item.campus_id if item.campus_id is not None else campus_id,
        movement_type=payload.movement_type,
        quantity=delta,
        previous_stock=previous_stock,
        new_stock=new_stock,
        reference_type=payload.reference_type or "MANUAL_ADJUSTMENT",
        reference_id=payload.reference_id,
        notes=payload.notes,
        performed_by_user_id=performed_by_user_id,
    )
    session.add(movement)
    await session.commit()
    await session.refresh(item)
    await session.refresh(movement)
    return item, movement


async def list_stock_movements(
    session: AsyncSession,
    item_id: Optional[int] = None,
    campus_id: Optional[int] = None,
    limit: int = 50,
) -> List[StockMovement]:
    query = select(StockMovement)
    if item_id is not None:
        query = query.where(StockMovement.item_id == item_id)
    if campus_id is not None:
        query = query.where(StockMovement.campus_id == campus_id)
    query = query.order_by(StockMovement.created_at.desc()).limit(limit)
    result = await session.exec(query)
    return result.all()


async def get_low_stock_alerts(
    session: AsyncSession,
    campus_id: Optional[int] = None,
) -> List[LowStockAlertRead]:
    query = select(InventoryItem).where(
        InventoryItem.is_active == True,
        InventoryItem.current_stock <= InventoryItem.min_stock_threshold,
    )
    if campus_id is not None:
        query = query.where(InventoryItem.campus_id == campus_id)

    items = (await session.exec(query)).all()
    alerts = []
    for it in items:
        alerts.append(
            LowStockAlertRead(
                item_id=it.id,
                sku=it.sku,
                name=it.name,
                category=it.category,
                current_stock=it.current_stock,
                min_stock_threshold=it.min_stock_threshold,
                unit_of_measure=it.unit_of_measure,
                deficit=max(0, it.min_stock_threshold - it.current_stock),
                location=it.location,
            )
        )
    return alerts


# ── Suppliers ──

async def create_supplier(
    session: AsyncSession,
    payload: SupplierCreate,
    campus_id: Optional[int] = None,
    org_id: Optional[int] = None,
) -> Supplier:
    supplier = Supplier(
        campus_id=payload.campus_id if payload.campus_id is not None else campus_id,
        org_id=payload.org_id if payload.org_id is not None else org_id,
        name=payload.name.strip(),
        contact_person=payload.contact_person,
        email=payload.email,
        phone=payload.phone,
        address=payload.address,
        tax_id=payload.tax_id,
        payment_terms=payload.payment_terms,
        is_active=True,
    )
    session.add(supplier)
    await session.commit()
    await session.refresh(supplier)
    return supplier


async def update_supplier(
    session: AsyncSession,
    supplier_id: int,
    payload: SupplierUpdate,
) -> Supplier:
    supplier = await session.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found.")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(supplier, key, value)

    supplier.updated_at = datetime.datetime.now(datetime.timezone.utc)
    session.add(supplier)
    await session.commit()
    await session.refresh(supplier)
    return supplier


async def delete_supplier(session: AsyncSession, supplier_id: int) -> None:
    supplier = await session.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found.")
    await session.delete(supplier)
    await session.commit()


async def get_supplier(session: AsyncSession, supplier_id: int) -> Supplier:
    supplier = await session.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found.")
    return supplier


async def list_suppliers(
    session: AsyncSession,
    campus_id: Optional[int] = None,
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Supplier]:
    query = select(Supplier)
    if campus_id is not None:
        query = query.where(Supplier.campus_id == campus_id)
    if is_active is not None:
        query = query.where(Supplier.is_active == is_active)
    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            or_(
                Supplier.name.ilike(search_pattern),
                Supplier.contact_person.ilike(search_pattern),
                Supplier.email.ilike(search_pattern),
            )
        )
    query = query.order_by(Supplier.name).offset(offset).limit(limit)
    result = await session.exec(query)
    return result.all()


# ── Purchase Orders Lifecycle ──

async def create_purchase_order(
    session: AsyncSession,
    payload: PurchaseOrderCreate,
    campus_id: Optional[int] = None,
    created_by_user_id: Optional[int] = None,
) -> Tuple[PurchaseOrder, List[PurchaseOrderItem]]:
    supplier = await session.get(Supplier, payload.supplier_id)
    if not supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found.")

    po_num = f"PO-{datetime.date.today().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

    subtotal = 0.0
    po_items_to_create = []

    for item_in in payload.items:
        inv_item = await session.get(InventoryItem, item_in.item_id)
        if not inv_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Inventory item ID {item_in.item_id} not found.",
            )
        line_total = round(item_in.quantity * item_in.unit_price, 2)
        subtotal += line_total
        po_items_to_create.append((item_in, line_total))

    total_amount = round(subtotal + payload.tax + payload.shipping_cost, 2)

    po = PurchaseOrder(
        po_number=po_num,
        supplier_id=payload.supplier_id,
        campus_id=payload.campus_id if payload.campus_id is not None else campus_id,
        status=PurchaseOrderStatusEnum.DRAFT,
        order_date=payload.order_date,
        expected_delivery_date=payload.expected_delivery_date,
        subtotal=subtotal,
        tax=payload.tax,
        shipping_cost=payload.shipping_cost,
        total_amount=total_amount,
        notes=payload.notes,
        created_by_user_id=created_by_user_id,
    )
    session.add(po)
    await session.commit()
    await session.refresh(po)

    created_items = []
    for item_in, line_total in po_items_to_create:
        poi = PurchaseOrderItem(
            po_id=po.id,
            item_id=item_in.item_id,
            quantity=item_in.quantity,
            unit_price=item_in.unit_price,
            received_quantity=0,
            total_price=line_total,
        )
        session.add(poi)
        created_items.append(poi)

    await session.commit()
    for ci in created_items:
        await session.refresh(ci)

    return po, created_items


async def approve_purchase_order(
    session: AsyncSession,
    po_id: int,
    approved_by_user_id: Optional[int] = None,
) -> PurchaseOrder:
    po = await session.get(PurchaseOrder, po_id)
    if not po:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found.")

    if po.status not in [PurchaseOrderStatusEnum.DRAFT, PurchaseOrderStatusEnum.PENDING_APPROVAL]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve PO in status '{po.status.value}'. Must be DRAFT or PENDING_APPROVAL.",
        )

    po.status = PurchaseOrderStatusEnum.APPROVED
    po.approved_by_user_id = approved_by_user_id
    po.approved_at = datetime.datetime.now(datetime.timezone.utc)
    po.updated_at = datetime.datetime.now(datetime.timezone.utc)
    session.add(po)
    await session.commit()
    await session.refresh(po)
    return po


async def receive_purchase_order(
    session: AsyncSession,
    po_id: int,
    payload: ReceivePurchaseOrderRequest,
    performed_by_user_id: Optional[int] = None,
) -> Tuple[PurchaseOrder, List[PurchaseOrderItem]]:
    po = await session.get(PurchaseOrder, po_id)
    if not po:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found.")

    if po.status not in [
        PurchaseOrderStatusEnum.APPROVED,
        PurchaseOrderStatusEnum.ORDERED,
        PurchaseOrderStatusEnum.PARTIALLY_RECEIVED,
    ]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot receive PO in status '{po.status.value}'. PO must be APPROVED, ORDERED, or PARTIALLY_RECEIVED.",
        )

    # Fetch PO items
    po_items = (await session.exec(select(PurchaseOrderItem).where(PurchaseOrderItem.po_id == po.id))).all()
    po_items_map = {item.item_id: item for item in po_items}

    for receive_item in payload.items:
        if receive_item.item_id not in po_items_map:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Item ID {receive_item.item_id} is not in this purchase order.",
            )

        poi = po_items_map[receive_item.item_id]
        new_received = poi.received_quantity + receive_item.quantity_received
        if new_received > poi.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Total received quantity ({new_received}) cannot exceed ordered quantity ({poi.quantity}) for item ID {poi.item_id}.",
            )
        poi.received_quantity = new_received
        session.add(poi)

        # Update stock of inventory item
        inv_item = await session.get(InventoryItem, poi.item_id)
        if inv_item:
            prev_stock = inv_item.current_stock
            inv_item.current_stock += receive_item.quantity_received
            inv_item.updated_at = datetime.datetime.now(datetime.timezone.utc)
            session.add(inv_item)

            # Log stock movement
            movement = StockMovement(
                item_id=inv_item.id,
                campus_id=po.campus_id,
                movement_type=StockMovementTypeEnum.PURCHASE,
                quantity=receive_item.quantity_received,
                previous_stock=prev_stock,
                new_stock=inv_item.current_stock,
                reference_type="PURCHASE_ORDER",
                reference_id=po.po_number,
                notes=payload.notes or f"Goods receipt for PO {po.po_number}",
                performed_by_user_id=performed_by_user_id,
            )
            session.add(movement)

    # Determine if PO is fully received
    all_fulfilled = all(item.received_quantity >= item.quantity for item in po_items)
    if all_fulfilled:
        po.status = PurchaseOrderStatusEnum.FULFILLED
        po.delivery_date = datetime.date.today()
    else:
        po.status = PurchaseOrderStatusEnum.PARTIALLY_RECEIVED

    po.updated_at = datetime.datetime.now(datetime.timezone.utc)
    session.add(po)
    await session.commit()
    await session.refresh(po)
    for it in po_items:
        await session.refresh(it)

    return po, po_items


async def cancel_purchase_order(session: AsyncSession, po_id: int) -> PurchaseOrder:
    po = await session.get(PurchaseOrder, po_id)
    if not po:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found.")

    if po.status in [PurchaseOrderStatusEnum.FULFILLED, PurchaseOrderStatusEnum.CANCELLED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel PO in status '{po.status.value}'.",
        )

    po.status = PurchaseOrderStatusEnum.CANCELLED
    po.updated_at = datetime.datetime.now(datetime.timezone.utc)
    session.add(po)
    await session.commit()
    await session.refresh(po)
    return po


async def get_purchase_order(
    session: AsyncSession,
    po_id: int,
) -> Tuple[PurchaseOrder, List[PurchaseOrderItem], Optional[Supplier]]:
    po = await session.get(PurchaseOrder, po_id)
    if not po:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found.")

    items = (await session.exec(select(PurchaseOrderItem).where(PurchaseOrderItem.po_id == po.id))).all()
    supplier = await session.get(Supplier, po.supplier_id)
    return po, items, supplier


async def list_purchase_orders(
    session: AsyncSession,
    campus_id: Optional[int] = None,
    supplier_id: Optional[int] = None,
    status_filter: Optional[PurchaseOrderStatusEnum] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[PurchaseOrder]:
    query = select(PurchaseOrder)
    if campus_id is not None:
        query = query.where(PurchaseOrder.campus_id == campus_id)
    if supplier_id is not None:
        query = query.where(PurchaseOrder.supplier_id == supplier_id)
    if status_filter is not None:
        query = query.where(PurchaseOrder.status == status_filter)

    query = query.order_by(PurchaseOrder.created_at.desc()).offset(offset).limit(limit)
    result = await session.exec(query)
    return result.all()


# ── Inventory Summary Metrics ──

async def get_inventory_summary(
    session: AsyncSession,
    campus_id: Optional[int] = None,
) -> InventorySummaryRead:
    item_query = select(InventoryItem).where(InventoryItem.is_active == True)
    if campus_id is not None:
        item_query = item_query.where(InventoryItem.campus_id == campus_id)
    items = (await session.exec(item_query)).all()

    total_items = len(items)
    total_stock_units = sum(it.current_stock for it in items)
    total_inventory_value = round(sum(it.current_stock * it.unit_price for it in items), 2)
    low_stock_count = sum(1 for it in items if it.current_stock <= it.min_stock_threshold)

    po_query = select(PurchaseOrder).where(
        PurchaseOrder.status.in_([
            PurchaseOrderStatusEnum.DRAFT,
            PurchaseOrderStatusEnum.PENDING_APPROVAL,
            PurchaseOrderStatusEnum.APPROVED,
            PurchaseOrderStatusEnum.ORDERED,
            PurchaseOrderStatusEnum.PARTIALLY_RECEIVED,
        ])
    )
    if campus_id is not None:
        po_query = po_query.where(PurchaseOrder.campus_id == campus_id)
    pending_pos = (await session.exec(po_query)).all()

    supp_query = select(Supplier).where(Supplier.is_active == True)
    if campus_id is not None:
        supp_query = supp_query.where(Supplier.campus_id == campus_id)
    suppliers = (await session.exec(supp_query)).all()

    return InventorySummaryRead(
        total_items=total_items,
        total_stock_units=total_stock_units,
        total_inventory_value=total_inventory_value,
        low_stock_count=low_stock_count,
        pending_po_count=len(pending_pos),
        total_suppliers=len(suppliers),
    )
