"""
台股布林通道交易訊號系統 - SQLAlchemy 資料模型

定義所有資料表結構，包含股價、訊號、交易紀錄及回測結果。
"""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    BigInteger,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """所有模型的基底類別"""
    pass


class StockPrice(Base):
    """
    股價資料表

    儲存每日 OHLCV（開盤、最高、最低、收盤、成交量）資料。
    以 (date, stock_id) 作為唯一鍵值，避免重複寫入。
    """
    __tablename__ = "stock_prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    stock_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("date", "stock_id", name="uq_stock_price_date_stock"),
        Index("ix_stock_price_stock_date", "stock_id", "date"),
    )

    def __repr__(self) -> str:
        return (
            f"<StockPrice(stock_id={self.stock_id}, date={self.date}, "
            f"close={self.close})>"
        )


class Signal(Base):
    """
    交易訊號資料表

    記錄由策略引擎產生的買賣訊號，包含訊號類型、觸發價格與趨勢方向。
    """
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    stock_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    signal_type: Mapped[str] = mapped_column(
        String(10), nullable=False, comment="BUY 或 SELL"
    )
    price: Mapped[float] = mapped_column(Float, nullable=False)
    trend_direction: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="UPTREND / DOWNTREND / SIDEWAYS"
    )
    details: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="訊號詳細描述"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        Index("ix_signal_stock_date", "stock_id", "date"),
    )

    def __repr__(self) -> str:
        return (
            f"<Signal(stock_id={self.stock_id}, date={self.date}, "
            f"type={self.signal_type}, price={self.price})>"
        )


class TradeRecord(Base):
    """
    交易日誌資料表

    紀錄每筆交易的買賣資訊，支援系統訊號與手動操作兩種來源。
    當賣出資訊填入後，自動計算損益與報酬率。
    """
    __tablename__ = "trade_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    stock_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    buy_price: Mapped[float] = mapped_column(Float, nullable=False)
    buy_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    buy_shares: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="買入股數（1 張 = 1000 股）"
    )
    sell_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sell_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    signal_source: Mapped[str] = mapped_column(
        String(10), nullable=False, default="MANUAL",
        comment="SYSTEM 或 MANUAL",
    )
    status: Mapped[str] = mapped_column(
        String(10), nullable=False, default="HOLDING",
        comment="HOLDING / CLOSED / STOPLOSS",
    )
    profit_loss: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="損益金額（新台幣）"
    )
    return_pct: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="報酬率（%）"
    )
    holding_days: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="持有天數"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<TradeRecord(id={self.id}, stock_id={self.stock_id}, "
            f"status={self.status}, P/L={self.profit_loss})>"
        )


class BacktestResult(Base):
    """
    回測結果資料表

    儲存每次回測的參數、績效指標及詳細交易紀錄（以 JSON 格式存放）。
    """
    __tablename__ = "backtest_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    params_json: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="回測參數 JSON"
    )
    total_trades: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    win_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_return: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="總報酬率（%）"
    )
    max_drawdown: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="最大回撤（%）"
    )
    results_json: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="詳細結果 JSON（交易列表、權益曲線等）"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<BacktestResult(id={self.id}, stock_id={self.stock_id}, "
            f"trades={self.total_trades}, return={self.total_return}%)>"
        )
