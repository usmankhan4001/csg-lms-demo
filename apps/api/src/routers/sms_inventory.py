import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import (
    KeycloakUserPrincipal,
    get_current_user_principal,
    require_roles,
)
from src.db.sms_inventory import (
    ItemCategoryEnum,
    PurchaseOrderStatusEnum,
    StockMovementTypeEnum,
)
from src.schemas.sms.inventory import (
    InventoryItemCreate,
    InventoryItemRead,
    InventoryItemUpdate,
    InventorySummaryRead,
    LowStockAlertRead,
    PurchaseOrderCreate,
    PurchaseOrderDetailRead,
    PurchaseOrderItemRead,
    PurchaseOrderRead,
    ReceivePurchaseOrderRequest,
    StockAdjustmentCreate,
    StockMovementRead,
    SupplierCreate,
    SupplierRead,
    SupplierUpdate,
)
from src.security.features_utils.dependencies import require_sms_inventory_feature
from src.security.school_ownership import (
    assert_campus_allowed,
    resolve_scoped_campus_id,
)
from src.services.sms import inventory as inventory_service

_INVENTORY_STAFF = ["SUPER_ADMIN", "SCHOOL_ADMIN", "STAFF", "PRINCIPAL"]

router = APIRouter(dependencies=[Depends(require_sms_inventory_feature)])


# ── Inventory Items ──

@router.post(
    "/items",
    response_model=InventoryItemRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Inventory Item",
)
async def create_item(
    payload: InventoryItemCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_INVENTORY_STAFF)),
) -> InventoryItemRead:
    assert_campus_allowed(principal, payload.campus_id)
    item = await inventory_service.create_inventory_item(
        session=session,
        payload=payload,
        campus_id=resolve_scoped_campus_id(principal, payload.campus_id),
        org_id=principal.org_id,
    )
    is_low = item.current_stock <= item.min_stock_threshold
    res = InventoryItemRead.model_validate(item)
    res.is_low_stock = is_low
    return res


@router.get(
    "/items",
    response_model=List[InventoryItemRead],
    summary="List Inventory Items",
)
async def list_items(
    campus_id: Optional[int] = None,
    category: Optional[ItemCategoryEnum] = None,
    low_stock_only: bool = False,
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_INVENTORY_STAFF)),
) -> List[InventoryItemRead]:
    scoped_campus = resolve_scoped_campus_id(principal, campus_id)
    items = await inventory_service.list_inventory_items(
        session=session,
        campus_id=scoped_campus,
        category=category,
        low_stock_only=low_stock_only,
        search=search,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )
    out = []
    for it in items:
        read = InventoryItemRead.model_validate(it)
        read.is_low_stock = it.current_stock <= it.min_stock_threshold
        out.append(read)
    return out


@router.get(
    "/items/low-stock",
    response_model=List[LowStockAlertRead],
    summary="Get Low Stock Alerts",
)
async def get_low_stock_alerts_endpoint(
    campus_id: Optional[int] = None,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_INVENTORY_STAFF)),
) -> List[LowStockAlertRead]:
    scoped_campus = resolve_scoped_campus_id(principal, campus_id)
    return await inventory_service.get_low_stock_alerts(session, campus_id=scoped_campus)


@router.get(
    "/items/{item_id}",
    response_model=InventoryItemRead,
    summary="Get Inventory Item Details",
)
async def get_item(
    item_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_INVENTORY_STAFF)),
) -> InventoryItemRead:
    item = await inventory_service.get_inventory_item(session, item_id)
    assert_campus_allowed(principal, item.campus_id)
    read = InventoryItemRead.model_validate(item)
    read.is_low_stock = item.current_stock <= item.min_stock_threshold
    return read


@router.patch(
    "/items/{item_id}",
    response_model=InventoryItemRead,
    summary="Update Inventory Item",
)
async def update_item(
    item_id: int,
    payload: InventoryItemUpdate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_INVENTORY_STAFF)),
) -> InventoryItemRead:
    existing = await inventory_service.get_inventory_item(session, item_id)
    assert_campus_allowed(principal, existing.campus_id)
    item = await inventory_service.update_inventory_item(session, item_id, payload)
    read = InventoryItemRead.model_validate(item)
    read.is_low_stock = item.current_stock <= item.min_stock_threshold
    return read


@router.delete(
    "/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Inventory Item",
)
async def delete_item(
    item_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_INVENTORY_STAFF)),
) -> None:
    existing = await inventory_service.get_inventory_item(session, item_id)
    assert_campus_allowed(principal, existing.campus_id)
    await inventory_service.delete_inventory_item(session, item_id)


@router.post(
    "/items/{item_id}/adjust-stock",
    response_model=InventoryItemRead,
    summary="Record Stock Adjustment",
)
async def adjust_stock_endpoint(
    item_id: int,
    payload: StockAdjustmentCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_INVENTORY_STAFF)),
) -> InventoryItemRead:
    existing = await inventory_service.get_inventory_item(session, item_id)
    assert_campus_allowed(principal, existing.campus_id)
    user_id = principal.raw_claims.get("lh_user_id")
    item, _ = await inventory_service.adjust_stock(
        session=session,
        item_id=item_id,
        payload=payload,
        performed_by_user_id=user_id,
        campus_id=existing.campus_id,
    )
    read = InventoryItemRead.model_validate(item)
    read.is_low_stock = item.current_stock <= item.min_stock_threshold
    return read


@router.get(
    "/items/{item_id}/movements",
    response_model=List[StockMovementRead],
    summary="Get Item Stock Audit Trail",
)
async def list_item_movements(
    item_id: int,
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_INVENTORY_STAFF)),
) -> List[StockMovementRead]:
    existing = await inventory_service.get_inventory_item(session, item_id)
    assert_campus_allowed(principal, existing.campus_id)
    movements = await inventory_service.list_stock_movements(session, item_id=item_id, limit=limit)
    return [StockMovementRead.model_validate(m) for m in movements]


# ── Suppliers ──

@router.post(
    "/suppliers",
    response_model=SupplierRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Supplier",
)
async def create_supplier_endpoint(
    payload: SupplierCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_INVENTORY_STAFF)),
) -> SupplierRead:
    assert_campus_allowed(principal, payload.campus_id)
    supplier = await inventory_service.create_supplier(
        session=session,
        payload=payload,
        campus_id=resolve_scoped_campus_id(principal, payload.campus_id),
        org_id=principal.org_id,
    )
    return SupplierRead.model_validate(supplier)


@router.get(
    "/suppliers",
    response_model=List[SupplierRead],
    summary="List Suppliers",
)
async def list_suppliers_endpoint(
    campus_id: Optional[int] = None,
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_INVENTORY_STAFF)),
) -> List[SupplierRead]:
    scoped_campus = resolve_scoped_campus_id(principal, campus_id)
    suppliers = await inventory_service.list_suppliers(
        session=session,
        campus_id=scoped_campus,
        search=search,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )
    return [SupplierRead.model_validate(s) for s in suppliers]


@router.get(
    "/suppliers/{supplier_id}",
    response_model=SupplierRead,
    summary="Get Supplier Details",
)
async def get_supplier_endpoint(
    supplier_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_INVENTORY_STAFF)),
) -> SupplierRead:
    supplier = await inventory_service.get_supplier(session, supplier_id)
    assert_campus_allowed(principal, supplier.campus_id)
    return SupplierRead.model_validate(supplier)


@router.patch(
    "/suppliers/{supplier_id}",
    response_model=SupplierRead,
    summary="Update Supplier",
)
async def update_supplier_endpoint(
    supplier_id: int,
    payload: SupplierUpdate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_INVENTORY_STAFF)),
) -> SupplierRead:
    existing = await inventory_service.get_supplier(session, supplier_id)
    assert_campus_allowed(principal, existing.campus_id)
    supplier = await inventory_service.update_supplier(session, supplier_id, payload)
    return SupplierRead.model_validate(supplier)


@router.delete(
    "/suppliers/{supplier_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Supplier",
)
async def delete_supplier_endpoint(
    supplier_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_INVENTORY_STAFF)),
) -> None:
    existing = await inventory_service.get_supplier(session, supplier_id)
    assert_campus_allowed(principal, existing.campus_id)
    await inventory_service.delete_supplier(session, supplier_id)


# ── Purchase Orders ──

@router.post(
    "/purchase-orders",
    response_model=PurchaseOrderDetailRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Purchase Order (Draft)",
)
async def create_purchase_order_endpoint(
    payload: PurchaseOrderCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_INVENTORY_STAFF)),
) -> PurchaseOrderDetailRead:
    assert_campus_allowed(principal, payload.campus_id)
    user_id = principal.raw_claims.get("lh_user_id")
    po, items = await inventory_service.create_purchase_order(
        session=session,
        payload=payload,
        campus_id=resolve_scoped_campus_id(principal, payload.campus_id),
        created_by_user_id=user_id,
    )
    supplier = await inventory_service.get_supplier(session, po.supplier_id)
    
    item_reads = []
    for it in items:
        inv_it = await inventory_service.get_inventory_item(session, it.item_id)
        ir = PurchaseOrderItemRead.model_validate(it)
        ir.item_name = inv_it.name if inv_it else None
        ir.item_sku = inv_it.sku if inv_it else None
        item_reads.append(ir)

    res = PurchaseOrderDetailRead.model_validate(po)
    res.supplier_name = supplier.name if supplier else None
    res.items = item_reads
    return res


@router.get(
    "/purchase-orders",
    response_model=List[PurchaseOrderRead],
    summary="List Purchase Orders",
)
async def list_purchase_orders_endpoint(
    campus_id: Optional[int] = None,
    supplier_id: Optional[int] = None,
    status_filter: Optional[PurchaseOrderStatusEnum] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_INVENTORY_STAFF)),
) -> List[PurchaseOrderRead]:
    scoped_campus = resolve_scoped_campus_id(principal, campus_id)
    pos = await inventory_service.list_purchase_orders(
        session=session,
        campus_id=scoped_campus,
        supplier_id=supplier_id,
        status_filter=status_filter,
        limit=limit,
        offset=offset,
    )
    out = []
    for po in pos:
        supplier = await session.get(inventory_service.Supplier, po.supplier_id)
        pr = PurchaseOrderRead.model_validate(po)
        pr.supplier_name = supplier.name if supplier else None
        out.append(pr)
    return out


@router.get(
    "/purchase-orders/{po_id}",
    response_model=PurchaseOrderDetailRead,
    summary="Get Purchase Order Details",
)
async def get_purchase_order_endpoint(
    po_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_INVENTORY_STAFF)),
) -> PurchaseOrderDetailRead:
    po, items, supplier = await inventory_service.get_purchase_order(session, po_id)
    assert_campus_allowed(principal, po.campus_id)
    
    item_reads = []
    for it in items:
        inv_it = await session.get(inventory_service.InventoryItem, it.item_id)
        ir = PurchaseOrderItemRead.model_validate(it)
        ir.item_name = inv_it.name if inv_it else None
        ir.item_sku = inv_it.sku if inv_it else None
        item_reads.append(ir)

    res = PurchaseOrderDetailRead.model_validate(po)
    res.supplier_name = supplier.name if supplier else None
    res.items = item_reads
    return res


@router.post(
    "/purchase-orders/{po_id}/approve",
    response_model=PurchaseOrderRead,
    summary="Approve Purchase Order",
)
async def approve_purchase_order_endpoint(
    po_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_INVENTORY_STAFF)),
) -> PurchaseOrderRead:
    existing, _, _ = await inventory_service.get_purchase_order(session, po_id)
    assert_campus_allowed(principal, existing.campus_id)
    user_id = principal.raw_claims.get("lh_user_id")
    po = await inventory_service.approve_purchase_order(session, po_id, approved_by_user_id=user_id)
    supplier = await session.get(inventory_service.Supplier, po.supplier_id)
    res = PurchaseOrderRead.model_validate(po)
    res.supplier_name = supplier.name if supplier else None
    return res


@router.post(
    "/purchase-orders/{po_id}/receive",
    response_model=PurchaseOrderDetailRead,
    summary="Receive Goods for Purchase Order",
)
async def receive_purchase_order_endpoint(
    po_id: int,
    payload: ReceivePurchaseOrderRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_INVENTORY_STAFF)),
) -> PurchaseOrderDetailRead:
    existing, _, _ = await inventory_service.get_purchase_order(session, po_id)
    assert_campus_allowed(principal, existing.campus_id)
    user_id = principal.raw_claims.get("lh_user_id")
    po, items = await inventory_service.receive_purchase_order(
        session=session,
        po_id=po_id,
        payload=payload,
        performed_by_user_id=user_id,
    )
    supplier = await session.get(inventory_service.Supplier, po.supplier_id)
    
    item_reads = []
    for it in items:
        inv_it = await session.get(inventory_service.InventoryItem, it.item_id)
        ir = PurchaseOrderItemRead.model_validate(it)
        ir.item_name = inv_it.name if inv_it else None
        ir.item_sku = inv_it.sku if inv_it else None
        item_reads.append(ir)

    res = PurchaseOrderDetailRead.model_validate(po)
    res.supplier_name = supplier.name if supplier else None
    res.items = item_reads
    return res


@router.post(
    "/purchase-orders/{po_id}/cancel",
    response_model=PurchaseOrderRead,
    summary="Cancel Purchase Order",
)
async def cancel_purchase_order_endpoint(
    po_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_INVENTORY_STAFF)),
) -> PurchaseOrderRead:
    existing, _, _ = await inventory_service.get_purchase_order(session, po_id)
    assert_campus_allowed(principal, existing.campus_id)
    po = await inventory_service.cancel_purchase_order(session, po_id)
    supplier = await session.get(inventory_service.Supplier, po.supplier_id)
    res = PurchaseOrderRead.model_validate(po)
    res.supplier_name = supplier.name if supplier else None
    return res


# ── Inventory Summary Metrics ──

@router.get(
    "/summary",
    response_model=InventorySummaryRead,
    summary="Get Inventory Summary Metrics",
)
async def get_summary_endpoint(
    campus_id: Optional[int] = None,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_INVENTORY_STAFF)),
) -> InventorySummaryRead:
    scoped_campus = resolve_scoped_campus_id(principal, campus_id)
    return await inventory_service.get_inventory_summary(session, campus_id=scoped_campus)
