import datetime
import pytest
from fastapi import HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_inventory import (
    InventoryItem,
    ItemCategoryEnum,
    PurchaseOrderStatusEnum,
    StockMovementTypeEnum,
    Supplier,
)
from src.schemas.sms.inventory import (
    InventoryItemCreate,
    InventoryItemUpdate,
    PurchaseOrderCreate,
    PurchaseOrderItemCreate,
    ReceiveItemPayload,
    ReceivePurchaseOrderRequest,
    StockAdjustmentCreate,
    SupplierCreate,
    SupplierUpdate,
)
from src.routers.sms_inventory import (
    adjust_stock_endpoint,
    approve_purchase_order_endpoint,
    cancel_purchase_order_endpoint,
    create_item,
    create_purchase_order_endpoint,
    create_supplier_endpoint,
    delete_item,
    delete_supplier_endpoint,
    get_item,
    get_low_stock_alerts_endpoint,
    get_purchase_order_endpoint,
    get_summary_endpoint,
    get_supplier_endpoint,
    list_item_movements,
    list_items,
    list_purchase_orders_endpoint,
    list_suppliers_endpoint,
    receive_purchase_order_endpoint,
    update_item,
    update_supplier_endpoint,
)
from src.tests.sms._principals import SUPERADMIN


@pytest.mark.asyncio
async def test_inventory_item_crud_and_search(db: AsyncSession):
    """Test creating, reading, updating, listing, and deleting inventory items."""
    # 1. Create items
    item1 = await create_item(
        payload=InventoryItemCreate(
            campus_id=1,
            sku="SKU-SCI-001",
            name="Microscope Slides (Box of 50)",
            category=ItemCategoryEnum.LAB_EQUIPMENT,
            unit_of_measure="boxes",
            current_stock=20,
            min_stock_threshold=5,
            unit_price=12.50,
            location="Lab Room 101",
        ),
        session=db,
        principal=SUPERADMIN,
    )
    assert item1.id is not None
    assert item1.current_stock == 20
    assert item1.is_low_stock is False

    item2 = await create_item(
        payload=InventoryItemCreate(
            campus_id=1,
            sku="SKU-STA-002",
            name="Whiteboard Markers (Pack of 12)",
            category=ItemCategoryEnum.STATIONERY,
            unit_of_measure="packs",
            current_stock=2,
            min_stock_threshold=10,
            unit_price=8.00,
            location="Staff Room Cupboard",
        ),
        session=db,
        principal=SUPERADMIN,
    )
    assert item2.id is not None
    assert item2.is_low_stock is True

    # 2. Duplicate SKU rejected
    with pytest.raises(HTTPException) as exc_info:
        await create_item(
            payload=InventoryItemCreate(
                campus_id=1,
                sku="SKU-SCI-001",
                name="Duplicate Item",
                category=ItemCategoryEnum.LAB_EQUIPMENT,
            ),
            session=db,
            principal=SUPERADMIN,
        )
    assert exc_info.value.status_code == 400

    # 3. Get item by ID
    fetched = await get_item(item_id=item1.id, session=db, principal=SUPERADMIN)
    assert fetched.name == "Microscope Slides (Box of 50)"

    # 4. Search and filter
    lab_items = await list_items(
        category=ItemCategoryEnum.LAB_EQUIPMENT,
        session=db,
        principal=SUPERADMIN,
        limit=100,
        offset=0,
    )
    assert len(lab_items) == 1
    assert lab_items[0].sku == "SKU-SCI-001"

    searched = await list_items(
        search="Whiteboard",
        session=db,
        principal=SUPERADMIN,        limit=100,
        offset=0,
    )
    assert len(searched) == 1
    assert searched[0].sku == "SKU-STA-002"

    # 5. Low stock filter
    low_stocks = await list_items(
        low_stock_only=True,
        session=db,
        principal=SUPERADMIN,        limit=100,
        offset=0,
    )
    assert len(low_stocks) == 1
    assert low_stocks[0].id == item2.id

    # 6. Update item
    updated = await update_item(
        item_id=item1.id,
        payload=InventoryItemUpdate(unit_price=15.00, location="Lab Cabinet B"),
        session=db,
        principal=SUPERADMIN,
    )
    assert updated.unit_price == 15.00
    assert updated.location == "Lab Cabinet B"

    # 7. Delete item
    await delete_item(item_id=item2.id, session=db, principal=SUPERADMIN)
    with pytest.raises(HTTPException) as exc_info:
        await get_item(item_id=item2.id, session=db, principal=SUPERADMIN)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_stock_adjustments_and_movements(db: AsyncSession):
    """Test stock adjustments (in, out, manual), audit trail, and negative stock prevention."""
    item = await create_item(
        payload=InventoryItemCreate(
            campus_id=1,
            sku="SKU-UNIF-01",
            name="School Blazer (Size M)",
            category=ItemCategoryEnum.UNIFORM,
            current_stock=10,
            min_stock_threshold=5,
            unit_price=45.00,
        ),
        session=db,
        principal=SUPERADMIN,
    )

    # 1. Stock Out (e.g. issued to students)
    adjusted = await adjust_stock_endpoint(
        item_id=item.id,
        payload=StockAdjustmentCreate(
            movement_type=StockMovementTypeEnum.OUT,
            quantity=4,
            reference_type="STUDENT_ISSUE",
            notes="Issued to Grade 10 batch",
        ),
        session=db,
        principal=SUPERADMIN,
    )
    assert adjusted.current_stock == 6

    # 2. Stock In (restock)
    adjusted2 = await adjust_stock_endpoint(
        item_id=item.id,
        payload=StockAdjustmentCreate(
            movement_type=StockMovementTypeEnum.IN,
            quantity=10,
            reference_type="DONATION",
            notes="Received alumni uniform batch",
        ),
        session=db,
        principal=SUPERADMIN,
    )
    assert adjusted2.current_stock == 16

    # 3. Negative stock prevention
    with pytest.raises(HTTPException) as exc_info:
        await adjust_stock_endpoint(
            item_id=item.id,
            payload=StockAdjustmentCreate(
                movement_type=StockMovementTypeEnum.OUT,
                quantity=50,
            ),
            session=db,
            principal=SUPERADMIN,
        )
    assert exc_info.value.status_code == 400

    # 4. Check movement audit log
    movements = await list_item_movements(item_id=item.id, session=db, principal=SUPERADMIN, limit=100)
    # Initial + Stock Out + Stock In = 3 movements
    assert len(movements) >= 3


@pytest.mark.asyncio
async def test_supplier_and_purchase_order_lifecycle(db: AsyncSession):
    """Test full procurement flow: supplier creation, PO draft, approval, receiving goods, and stock auto-update."""
    # 1. Create Supplier
    supplier = await create_supplier_endpoint(
        payload=SupplierCreate(
            campus_id=1,
            name="Global School Supplies Ltd",
            contact_person="Alice Vendor",
            email="sales@globalsupplies.com",
            phone="+1234567890",
            address="100 Commercial Way",
            payment_terms="Net 30",
        ),
        session=db,
        principal=SUPERADMIN,
    )
    assert supplier.id is not None
    assert supplier.name == "Global School Supplies Ltd"

    # 2. Create Items for procurement
    item1 = await create_item(
        payload=InventoryItemCreate(
            campus_id=1,
            sku="SKU-TEXT-01",
            name="Physics Grade 11 Textbook",
            category=ItemCategoryEnum.TEXTBOOK,
            current_stock=5,
            min_stock_threshold=15,
            unit_price=30.00,
        ),
        session=db,
        principal=SUPERADMIN,
    )
    item2 = await create_item(
        payload=InventoryItemCreate(
            campus_id=1,
            sku="SKU-SPORT-01",
            name="Soccer Balls (FIFA standard)",
            category=ItemCategoryEnum.SPORTS,
            current_stock=2,
            min_stock_threshold=10,
            unit_price=20.00,
        ),
        session=db,
        principal=SUPERADMIN,
    )

    # 3. Create PO (Draft)
    po = await create_purchase_order_endpoint(
        payload=PurchaseOrderCreate(
            supplier_id=supplier.id,
            campus_id=1,
            order_date=datetime.date.today(),
            expected_delivery_date=datetime.date.today() + datetime.timedelta(days=7),
            tax=25.00,
            shipping_cost=15.00,
            notes="Urgent term start supplies",
            items=[
                PurchaseOrderItemCreate(item_id=item1.id, quantity=20, unit_price=28.00),
                PurchaseOrderItemCreate(item_id=item2.id, quantity=10, unit_price=18.00),
            ],
        ),
        session=db,
        principal=SUPERADMIN,
    )
    assert po.id is not None
    assert po.status == PurchaseOrderStatusEnum.DRAFT
    # Subtotal: (20 * 28) + (10 * 18) = 560 + 180 = 740. Total: 740 + 25 + 15 = 780.0
    assert po.subtotal == 740.0
    assert po.total_amount == 780.0
    assert len(po.items) == 2

    # 4. Approve PO
    approved_po = await approve_purchase_order_endpoint(
        po_id=po.id,
        session=db,
        principal=SUPERADMIN,
    )
    assert approved_po.status == PurchaseOrderStatusEnum.APPROVED
    assert approved_po.approved_at is not None

    # 5. Receive goods in batches (Partial receipt)
    partial_received = await receive_purchase_order_endpoint(
        po_id=po.id,
        payload=ReceivePurchaseOrderRequest(
            items=[
                ReceiveItemPayload(item_id=item1.id, quantity_received=10),
            ],
            notes="First batch of physics books arrived",
        ),
        session=db,
        principal=SUPERADMIN,
    )
    assert partial_received.status == PurchaseOrderStatusEnum.PARTIALLY_RECEIVED

    # Verify item1 stock increased: 5 + 10 = 15
    refreshed_item1 = await get_item(item_id=item1.id, session=db, principal=SUPERADMIN)
    assert refreshed_item1.current_stock == 15

    # 6. Receive remainder (Fulfilled)
    fulfilled_po = await receive_purchase_order_endpoint(
        po_id=po.id,
        payload=ReceivePurchaseOrderRequest(
            items=[
                ReceiveItemPayload(item_id=item1.id, quantity_received=10),
                ReceiveItemPayload(item_id=item2.id, quantity_received=10),
            ],
            notes="Remaining items received in good condition",
        ),
        session=db,
        principal=SUPERADMIN,
    )
    assert fulfilled_po.status == PurchaseOrderStatusEnum.FULFILLED
    assert fulfilled_po.delivery_date is not None

    # Verify both items reached their full received quantities and stock
    refreshed_item1 = await get_item(item_id=item1.id, session=db, principal=SUPERADMIN)
    assert refreshed_item1.current_stock == 25  # 5 initial + 20 received

    refreshed_item2 = await get_item(item_id=item2.id, session=db, principal=SUPERADMIN)
    assert refreshed_item2.current_stock == 12  # 2 initial + 10 received

    # 7. Summary metrics
    summary = await get_summary_endpoint(campus_id=1, session=db, principal=SUPERADMIN)
    assert summary.total_items >= 2
    assert summary.total_suppliers >= 1
    assert summary.total_inventory_value > 0
    
