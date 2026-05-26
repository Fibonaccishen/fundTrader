from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.fund import Fund
from ..models.holding import Holding
from ..models.transaction import Transaction
from ..schemas.schemas import TransactionCreate, TransactionOut, TransactionUpdate
from ..services.fund_data import get_or_create_fund, save_nav_history_to_db
from ..services.portfolio import update_holding_from_transactions

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.get("", response_model=list[TransactionOut])
async def list_transactions(
    fund_id: int | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List transactions, optionally filtered by fund."""
    query = select(Transaction).order_by(Transaction.transaction_date.desc(), Transaction.created_at.desc())
    if fund_id:
        query = query.where(Transaction.fund_id == fund_id)
    query = query.limit(limit)
    result = await db.execute(query)
    transactions = result.scalars().all()

    return [
        TransactionOut(
            id=t.id,
            fund_id=t.fund_id,
            fund_code=t.fund.code if t.fund else "",
            fund_name=t.fund.name if t.fund else "",
            holding_id=t.holding_id,
            transaction_type=t.transaction_type,
            transaction_date=t.transaction_date,
            amount=t.amount,
            nav_at_purchase=t.nav_at_purchase,
            shares=t.shares,
            fee=t.fee,
            platform=t.platform,
            notes=t.notes,
            created_at=t.created_at,
        )
        for t in transactions
    ]


@router.post("", response_model=TransactionOut, status_code=201)
async def create_transaction(data: TransactionCreate, db: AsyncSession = Depends(get_db)):
    """Record a new buy/sell transaction. Creates fund and holding records as needed."""
    if data.transaction_type not in ("buy", "sell"):
        raise HTTPException(status_code=400, detail="transaction_type must be 'buy' or 'sell'")

    # Find or create fund
    fund = await get_or_create_fund(db, data.fund_code)
    if not fund:
        raise HTTPException(status_code=400, detail=f"Could not find fund with code {data.fund_code}")

    # Calculate shares = amount / nav, minus fee for buys
    if data.transaction_type == "buy":
        effective_amount = data.amount - data.fee
    else:
        effective_amount = data.amount
    shares = (effective_amount / data.nav_at_purchase).quantize(Decimal("0.0001"))

    # Find or create holding for this fund
    result = await db.execute(
        select(Holding).where(Holding.fund_id == fund.id, Holding.status == "active")
    )
    holding = result.scalar_one_or_none()
    if not holding:
        if data.transaction_type == "buy":
            holding = Holding(fund_id=fund.id, strategy_type=data.strategy_type or "long_term")
            db.add(holding)
            await db.flush()
        else:
            raise HTTPException(status_code=400, detail="Cannot sell a fund with no active holding")

    # Create transaction
    txn = Transaction(
        fund_id=fund.id,
        holding_id=holding.id,
        transaction_type=data.transaction_type,
        transaction_date=data.transaction_date,
        amount=data.amount,
        nav_at_purchase=data.nav_at_purchase,
        shares=shares,
        fee=data.fee,
        platform=data.platform,
        notes=data.notes,
    )
    db.add(txn)
    await db.flush()

    # Recalculate holding
    await update_holding_from_transactions(db, holding)

    # Fetch NAV history for this fund
    try:
        from ..services.fund_data import fetch_and_save_nav
        await fetch_and_save_nav(db, fund.id, fund.code)
    except Exception:
        pass

    return TransactionOut(
        id=txn.id,
        fund_id=txn.fund_id,
        fund_code=fund.code,
        fund_name=fund.name,
        holding_id=txn.holding_id,
        transaction_type=txn.transaction_type,
        transaction_date=txn.transaction_date,
        amount=txn.amount,
        nav_at_purchase=txn.nav_at_purchase,
        shares=txn.shares,
        fee=txn.fee,
        platform=txn.platform,
        notes=txn.notes,
        created_at=txn.created_at,
    )


@router.patch("/{transaction_id}", response_model=TransactionOut)
async def update_transaction(transaction_id: int, data: TransactionUpdate, db: AsyncSession = Depends(get_db)):
    """Edit a transaction and recalculate holding."""
    result = await db.execute(select(Transaction).where(Transaction.id == transaction_id))
    txn = result.scalar_one_or_none()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if data.transaction_type is not None:
        txn.transaction_type = data.transaction_type
    if data.transaction_date is not None:
        txn.transaction_date = data.transaction_date
    if data.amount is not None:
        txn.amount = data.amount
    if data.nav_at_purchase is not None:
        txn.nav_at_purchase = data.nav_at_purchase
    if data.fee is not None:
        txn.fee = data.fee
    if data.platform is not None:
        txn.platform = data.platform
    if data.notes is not None:
        txn.notes = data.notes

    # Recalculate shares
    if data.transaction_type == "buy":
        effective = txn.amount - (txn.fee or 0)
    else:
        effective = txn.amount
    if txn.nav_at_purchase and txn.nav_at_purchase > 0:
        txn.shares = (effective / txn.nav_at_purchase).quantize(Decimal("0.0001"))
    await db.flush()

    # Recalculate holding
    result = await db.execute(select(Holding).where(Holding.id == txn.holding_id))
    holding = result.scalar_one_or_none()
    if holding:
        await update_holding_from_transactions(db, holding)

    return TransactionOut(
        id=txn.id, fund_id=txn.fund_id,
        fund_code=txn.fund.code if txn.fund else "",
        fund_name=txn.fund.name if txn.fund else "",
        holding_id=txn.holding_id,
        transaction_type=txn.transaction_type, transaction_date=txn.transaction_date,
        amount=txn.amount, nav_at_purchase=txn.nav_at_purchase,
        shares=txn.shares, fee=txn.fee or 0,
        platform=txn.platform or "", notes=txn.notes,
        created_at=txn.created_at,
    )


@router.delete("/{transaction_id}")
async def delete_transaction(transaction_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a transaction and recalculate holding."""
    result = await db.execute(select(Transaction).where(Transaction.id == transaction_id))
    txn = result.scalar_one_or_none()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")

    holding_id = txn.holding_id
    await db.delete(txn)
    await db.flush()

    # Recalculate holding
    result = await db.execute(select(Holding).where(Holding.id == holding_id))
    holding = result.scalar_one_or_none()
    if holding:
        await update_holding_from_transactions(db, holding)

    return {"message": "Transaction deleted"}
