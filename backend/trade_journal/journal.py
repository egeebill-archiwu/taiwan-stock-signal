"""
台股布林通道交易訊號系統 - 交易日誌 CRUD 模組

提供交易紀錄的新增、查詢、更新、刪除功能。
當填入賣出資訊時，自動計算損益、報酬率及持有天數。
"""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from backend.data.models import TradeRecord

logger = logging.getLogger(__name__)


def create_trade(db: Session, trade_data: dict) -> TradeRecord:
    """
    新增交易紀錄

    Parameters
    ----------
    db : Session
        資料庫 Session
    trade_data : dict
        交易資料，必填欄位：stock_id, buy_price, buy_time, buy_shares
        可選欄位：stock_name, note, signal_source, status

    Returns
    -------
    TradeRecord
        新建立的交易紀錄
    """
    # 處理買入時間格式
    buy_time = trade_data.get("buy_time")
    if isinstance(buy_time, str):
        buy_time = datetime.fromisoformat(buy_time)

    trade = TradeRecord(
        stock_id=trade_data["stock_id"],
        stock_name=trade_data.get("stock_name", ""),
        buy_price=trade_data["buy_price"],
        buy_time=buy_time,
        buy_shares=trade_data["buy_shares"],
        note=trade_data.get("note", ""),
        signal_source=trade_data.get("signal_source", "MANUAL"),
        status=trade_data.get("status", "HOLDING"),
    )

    # 如果同時提供了賣出資訊，一併處理
    if trade_data.get("sell_price") is not None and trade_data.get("sell_time") is not None:
        trade = _apply_sell_data(trade, trade_data)

    db.add(trade)
    db.commit()
    db.refresh(trade)

    logger.info(f"新增交易紀錄 #{trade.id}: {trade.stock_id} @ {trade.buy_price}")
    return trade


def update_trade(db: Session, trade_id: int, trade_data: dict) -> Optional[TradeRecord]:
    """
    更新交易紀錄

    當提供賣出價格與時間時，自動計算損益、報酬率、持有天數。

    Parameters
    ----------
    db : Session
        資料庫 Session
    trade_id : int
        交易紀錄 ID
    trade_data : dict
        要更新的欄位

    Returns
    -------
    TradeRecord or None
        更新後的交易紀錄，若找不到則回傳 None
    """
    trade = db.query(TradeRecord).filter(TradeRecord.id == trade_id).first()
    if trade is None:
        logger.warning(f"找不到交易紀錄 #{trade_id}")
        return None

    # 更新基本欄位
    updatable_fields = [
        "stock_id", "stock_name", "buy_price", "buy_time", "buy_shares",
        "note", "signal_source", "status",
    ]
    for field_name in updatable_fields:
        if field_name in trade_data:
            value = trade_data[field_name]
            if field_name in ("buy_time", "sell_time") and isinstance(value, str):
                value = datetime.fromisoformat(value)
            setattr(trade, field_name, value)

    # 處理賣出資訊並計算損益
    if "sell_price" in trade_data or "sell_time" in trade_data:
        trade = _apply_sell_data(trade, trade_data)

    trade.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(trade)

    logger.info(f"更新交易紀錄 #{trade_id}")
    return trade


def delete_trade(db: Session, trade_id: int) -> bool:
    """
    刪除交易紀錄

    Parameters
    ----------
    db : Session
        資料庫 Session
    trade_id : int
        交易紀錄 ID

    Returns
    -------
    bool
        是否成功刪除
    """
    trade = db.query(TradeRecord).filter(TradeRecord.id == trade_id).first()
    if trade is None:
        logger.warning(f"找不到交易紀錄 #{trade_id}")
        return False

    db.delete(trade)
    db.commit()
    logger.info(f"刪除交易紀錄 #{trade_id}")
    return True


def get_trade(db: Session, trade_id: int) -> Optional[TradeRecord]:
    """
    取得單筆交易紀錄

    Parameters
    ----------
    db : Session
        資料庫 Session
    trade_id : int
        交易紀錄 ID

    Returns
    -------
    TradeRecord or None
    """
    return db.query(TradeRecord).filter(TradeRecord.id == trade_id).first()


def get_all_trades(
    db: Session,
    stock_id: Optional[str] = None,
    status: Optional[str] = None,
    signal_source: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[TradeRecord]:
    """
    查詢交易紀錄列表，支援篩選條件

    Parameters
    ----------
    db : Session
        資料庫 Session
    stock_id : str, optional
        篩選股票代號
    status : str, optional
        篩選狀態（HOLDING / CLOSED / STOPLOSS）
    signal_source : str, optional
        篩選訊號來源（SYSTEM / MANUAL）
    limit : int
        回傳筆數上限
    offset : int
        分頁偏移量

    Returns
    -------
    list[TradeRecord]
        交易紀錄列表
    """
    query = db.query(TradeRecord)

    if stock_id:
        query = query.filter(TradeRecord.stock_id == stock_id)
    if status:
        query = query.filter(TradeRecord.status == status)
    if signal_source:
        query = query.filter(TradeRecord.signal_source == signal_source)

    # 依建立時間降冪排序
    query = query.order_by(TradeRecord.created_at.desc())

    return query.offset(offset).limit(limit).all()


def _apply_sell_data(trade: TradeRecord, data: dict) -> TradeRecord:
    """
    套用賣出資訊並自動計算損益相關欄位

    Parameters
    ----------
    trade : TradeRecord
        交易紀錄物件
    data : dict
        包含 sell_price 和 sell_time 的字典

    Returns
    -------
    TradeRecord
        更新後的交易紀錄
    """
    if "sell_price" in data and data["sell_price"] is not None:
        trade.sell_price = data["sell_price"]

    if "sell_time" in data and data["sell_time"] is not None:
        sell_time = data["sell_time"]
        if isinstance(sell_time, str):
            sell_time = datetime.fromisoformat(sell_time)
        trade.sell_time = sell_time

    # 計算損益（需要買賣價格和股數都齊全）
    if trade.sell_price is not None and trade.buy_price and trade.buy_shares:
        buy_amount = trade.buy_price * trade.buy_shares
        sell_amount = trade.sell_price * trade.buy_shares
        trade.profit_loss = round(sell_amount - buy_amount, 2)
        trade.return_pct = round(
            (trade.profit_loss / buy_amount) * 100, 2
        ) if buy_amount > 0 else 0.0

    # 計算持有天數
    if trade.sell_time is not None and trade.buy_time is not None:
        delta = trade.sell_time - trade.buy_time
        trade.holding_days = delta.days

    # 更新狀態
    if trade.sell_price is not None:
        status = data.get("status", "CLOSED")
        trade.status = status

    return trade


def trade_to_dict(trade: TradeRecord) -> dict:
    """
    將 TradeRecord ORM 物件轉換為字典

    Parameters
    ----------
    trade : TradeRecord
        交易紀錄

    Returns
    -------
    dict
        序列化後的字典
    """
    return {
        "id": trade.id,
        "stock_id": trade.stock_id,
        "stock_name": trade.stock_name,
        "buy_price": trade.buy_price,
        "buy_time": trade.buy_time.isoformat() if trade.buy_time else None,
        "buy_shares": trade.buy_shares,
        "sell_price": trade.sell_price,
        "sell_time": trade.sell_time.isoformat() if trade.sell_time else None,
        "note": trade.note,
        "signal_source": trade.signal_source,
        "status": trade.status,
        "profit_loss": trade.profit_loss,
        "return_pct": trade.return_pct,
        "holding_days": trade.holding_days,
        "created_at": trade.created_at.isoformat() if trade.created_at else None,
        "updated_at": trade.updated_at.isoformat() if trade.updated_at else None,
    }
