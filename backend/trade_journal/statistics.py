"""
台股布林通道交易訊號系統 - 交易統計模組

計算投資組合的整體績效統計、累積損益曲線及月報酬分析。
"""

import logging
from collections import defaultdict
from datetime import datetime
from typing import Optional

from backend.data.models import TradeRecord

logger = logging.getLogger(__name__)


def calculate_portfolio_stats(trades: list[TradeRecord]) -> dict:
    """
    計算投資組合整體統計

    Parameters
    ----------
    trades : list[TradeRecord]
        交易紀錄列表

    Returns
    -------
    dict
        統計指標字典
    """
    if not trades:
        return {
            "total_trades": 0,
            "holding_trades": 0,
            "closed_trades": 0,
            "total_profit_loss": 0.0,
            "realized_profit_loss": 0.0,
            "win_rate": 0.0,
            "avg_return_pct": 0.0,
            "best_trade_return": 0.0,
            "worst_trade_return": 0.0,
            "avg_holding_days": 0.0,
            "total_invested": 0.0,
            "current_holding_value": 0.0,
        }

    # 基本統計
    total = len(trades)
    holding = [t for t in trades if t.status == "HOLDING"]
    closed = [t for t in trades if t.status in ("CLOSED", "STOPLOSS")]

    # 已實現損益
    realized_pnl = sum(
        t.profit_loss for t in closed if t.profit_loss is not None
    )

    # 勝率（僅計算已結算的交易）
    winners = [t for t in closed if t.profit_loss is not None and t.profit_loss > 0]
    win_rate = round(len(winners) / len(closed) * 100, 2) if closed else 0.0

    # 報酬率統計
    returns = [t.return_pct for t in closed if t.return_pct is not None]
    avg_return = round(sum(returns) / len(returns), 2) if returns else 0.0
    best_return = round(max(returns), 2) if returns else 0.0
    worst_return = round(min(returns), 2) if returns else 0.0

    # 持有天數
    hold_days = [t.holding_days for t in closed if t.holding_days is not None]
    avg_hold = round(sum(hold_days) / len(hold_days), 1) if hold_days else 0.0

    # 投入金額
    total_invested = sum(
        t.buy_price * t.buy_shares for t in trades
        if t.buy_price is not None and t.buy_shares is not None
    )

    # 目前持有部位市值（以買入價估算，實際應以市價計算）
    current_holding = sum(
        t.buy_price * t.buy_shares for t in holding
        if t.buy_price is not None and t.buy_shares is not None
    )

    return {
        "total_trades": total,
        "holding_trades": len(holding),
        "closed_trades": len(closed),
        "total_profit_loss": round(realized_pnl, 2),
        "realized_profit_loss": round(realized_pnl, 2),
        "win_rate": win_rate,
        "avg_return_pct": avg_return,
        "best_trade_return": best_return,
        "worst_trade_return": worst_return,
        "avg_holding_days": avg_hold,
        "total_invested": round(total_invested, 2),
        "current_holding_value": round(current_holding, 2),
    }


def get_equity_curve(trades: list[TradeRecord]) -> list[dict]:
    """
    計算累積損益曲線

    以每筆已結算交易的賣出時間為基準，計算累積損益。

    Parameters
    ----------
    trades : list[TradeRecord]
        交易紀錄列表

    Returns
    -------
    list[dict]
        每個點包含 date 和 cumulative_pnl
    """
    # 只處理已結算的交易
    closed = [
        t for t in trades
        if t.status in ("CLOSED", "STOPLOSS")
        and t.sell_time is not None
        and t.profit_loss is not None
    ]

    if not closed:
        return []

    # 按賣出時間排序
    closed.sort(key=lambda t: t.sell_time)

    curve = []
    cumulative_pnl = 0.0

    for trade in closed:
        cumulative_pnl += trade.profit_loss
        sell_date = trade.sell_time
        if isinstance(sell_date, datetime):
            sell_date = sell_date.date()

        curve.append({
            "date": sell_date.isoformat(),
            "cumulative_pnl": round(cumulative_pnl, 2),
            "trade_pnl": round(trade.profit_loss, 2),
            "stock_id": trade.stock_id,
            "return_pct": trade.return_pct,
        })

    return curve


def get_monthly_returns(trades: list[TradeRecord]) -> list[dict]:
    """
    計算月度報酬分析

    以每筆已結算交易的賣出月份為基準，計算各月的損益統計。

    Parameters
    ----------
    trades : list[TradeRecord]
        交易紀錄列表

    Returns
    -------
    list[dict]
        每月的統計資料，包含 month, total_pnl, trade_count, win_count, win_rate
    """
    # 只處理已結算的交易
    closed = [
        t for t in trades
        if t.status in ("CLOSED", "STOPLOSS")
        and t.sell_time is not None
        and t.profit_loss is not None
    ]

    if not closed:
        return []

    # 按月份分組
    monthly: dict[str, list[TradeRecord]] = defaultdict(list)
    for trade in closed:
        sell_time = trade.sell_time
        if isinstance(sell_time, datetime):
            month_key = sell_time.strftime("%Y-%m")
        else:
            month_key = str(sell_time)[:7]
        monthly[month_key].append(trade)

    # 計算各月統計
    result = []
    for month_key in sorted(monthly.keys()):
        month_trades = monthly[month_key]
        total_pnl = sum(t.profit_loss for t in month_trades if t.profit_loss is not None)
        win_count = sum(
            1 for t in month_trades
            if t.profit_loss is not None and t.profit_loss > 0
        )
        trade_count = len(month_trades)

        result.append({
            "month": month_key,
            "total_pnl": round(total_pnl, 2),
            "trade_count": trade_count,
            "win_count": win_count,
            "loss_count": trade_count - win_count,
            "win_rate": round(win_count / trade_count * 100, 2) if trade_count > 0 else 0.0,
            "avg_pnl": round(total_pnl / trade_count, 2) if trade_count > 0 else 0.0,
        })

    return result


def get_stock_breakdown(trades: list[TradeRecord]) -> list[dict]:
    """
    依股票分組的交易統計

    Parameters
    ----------
    trades : list[TradeRecord]
        交易紀錄列表

    Returns
    -------
    list[dict]
        各股票的統計資料
    """
    stock_groups: dict[str, list[TradeRecord]] = defaultdict(list)
    for trade in trades:
        stock_groups[trade.stock_id].append(trade)

    result = []
    for stock_id in sorted(stock_groups.keys()):
        group = stock_groups[stock_id]
        closed = [t for t in group if t.status in ("CLOSED", "STOPLOSS")]
        pnls = [t.profit_loss for t in closed if t.profit_loss is not None]
        total_pnl = sum(pnls) if pnls else 0.0
        win_count = sum(1 for p in pnls if p > 0)

        result.append({
            "stock_id": stock_id,
            "stock_name": group[0].stock_name or "",
            "total_trades": len(group),
            "closed_trades": len(closed),
            "holding_trades": len(group) - len(closed),
            "total_pnl": round(total_pnl, 2),
            "win_rate": round(win_count / len(closed) * 100, 2) if closed else 0.0,
        })

    # 依總損益降冪排序
    result.sort(key=lambda x: x["total_pnl"], reverse=True)
    return result
