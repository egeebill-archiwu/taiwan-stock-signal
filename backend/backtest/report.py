"""
台股布林通道交易訊號系統 - 回測報告模組

從回測結果計算績效指標並產生格式化報告。
"""

import logging
from typing import Optional

from backend.backtest.engine import BacktestOutput, BacktestTrade, BacktestMetrics

logger = logging.getLogger(__name__)


def calculate_metrics(trades: list[BacktestTrade]) -> dict:
    """
    計算交易列表的績效指標

    Parameters
    ----------
    trades : list[BacktestTrade]
        已完成的交易列表

    Returns
    -------
    dict
        績效指標字典
    """
    if not trades:
        return {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0.0,
            "avg_return": 0.0,
            "total_profit_loss": 0.0,
            "max_single_win": 0.0,
            "max_single_loss": 0.0,
            "avg_holding_days": 0.0,
            "profit_factor": 0.0,
        }

    winning = [t for t in trades if t.profit_loss is not None and t.profit_loss > 0]
    losing = [t for t in trades if t.profit_loss is not None and t.profit_loss <= 0]

    total_profit = sum(t.profit_loss for t in winning if t.profit_loss is not None)
    total_loss = abs(sum(t.profit_loss for t in losing if t.profit_loss is not None))

    returns = [t.return_pct for t in trades if t.return_pct is not None]
    pnls = [t.profit_loss for t in trades if t.profit_loss is not None]
    hold_days = [t.holding_days for t in trades if t.holding_days is not None]

    return {
        "total_trades": len(trades),
        "winning_trades": len(winning),
        "losing_trades": len(losing),
        "win_rate": round(len(winning) / len(trades) * 100, 2) if trades else 0.0,
        "avg_return": round(sum(returns) / len(returns), 2) if returns else 0.0,
        "total_profit_loss": round(sum(pnls), 2) if pnls else 0.0,
        "max_single_win": round(max(pnls), 2) if pnls else 0.0,
        "max_single_loss": round(min(pnls), 2) if pnls else 0.0,
        "avg_holding_days": round(sum(hold_days) / len(hold_days), 1) if hold_days else 0.0,
        "profit_factor": round(total_profit / total_loss, 2) if total_loss > 0 else (99.9 if total_profit > 0 else 0.0),
    }


def generate_report(backtest_result: BacktestOutput) -> dict:
    """
    產生格式化的回測報告

    Parameters
    ----------
    backtest_result : BacktestOutput
        回測引擎的輸出結果

    Returns
    -------
    dict
        結構化報告字典，包含摘要、指標、交易明細、權益曲線
    """
    metrics = backtest_result.metrics
    trade_metrics = calculate_metrics(backtest_result.trades)

    # 產生交易明細列表
    trade_details = []
    for t in backtest_result.trades:
        trade_details.append({
            "stock_id": t.stock_id,
            "buy_date": t.buy_date,
            "buy_price": t.buy_price,
            "buy_shares": t.buy_shares,
            "sell_date": t.sell_date,
            "sell_price": t.sell_price,
            "profit_loss": t.profit_loss,
            "return_pct": t.return_pct,
            "holding_days": t.holding_days,
        })

    report = {
        "summary": {
            "stock_id": backtest_result.stock_id,
            "period": f"{backtest_result.start_date} ~ {backtest_result.end_date}",
            "initial_capital": metrics.initial_capital,
            "final_capital": metrics.final_capital,
            "total_return_pct": metrics.total_return,
            "total_return_amount": round(
                metrics.final_capital - metrics.initial_capital, 2
            ),
        },
        "parameters": backtest_result.params,
        "performance": {
            "total_trades": metrics.total_trades,
            "winning_trades": metrics.winning_trades,
            "losing_trades": metrics.losing_trades,
            "win_rate": metrics.win_rate,
            "avg_return": metrics.avg_return,
            "max_drawdown": metrics.max_drawdown,
            "sharpe_ratio": metrics.sharpe_ratio,
            "max_holding_days": metrics.max_holding_days,
            "avg_holding_days": metrics.avg_holding_days,
            "profit_factor": trade_metrics["profit_factor"],
            "max_single_win": trade_metrics["max_single_win"],
            "max_single_loss": trade_metrics["max_single_loss"],
        },
        "trades": trade_details,
        "equity_curve": backtest_result.equity_curve,
    }

    logger.info(
        f"回測報告產生完成 - {backtest_result.stock_id}："
        f"{metrics.total_trades} 筆交易，勝率 {metrics.win_rate}%，"
        f"報酬 {metrics.total_return}%"
    )

    return report


def format_report_text(backtest_result: BacktestOutput) -> str:
    """
    產生文字格式的回測報告（用於 Telegram 或終端顯示）

    Parameters
    ----------
    backtest_result : BacktestOutput
        回測結果

    Returns
    -------
    str
        格式化的報告文字
    """
    m = backtest_result.metrics
    trade_metrics = calculate_metrics(backtest_result.trades)

    lines = [
        "=" * 50,
        f"📊 回測報告 - {backtest_result.stock_id}",
        "=" * 50,
        f"📅 回測期間：{backtest_result.start_date} ~ {backtest_result.end_date}",
        f"💰 初始資金：{m.initial_capital:>14,.0f} 元",
        f"💰 最終資金：{m.final_capital:>14,.0f} 元",
        f"📈 總報酬率：{m.total_return:>13.2f} %",
        f"📉 最大回撤：{m.max_drawdown:>13.2f} %",
        "",
        "--- 交易統計 ---",
        f"🔢 總交易數：{m.total_trades:>6d} 筆",
        f"✅ 獲利筆數：{m.winning_trades:>6d} 筆",
        f"❌ 虧損筆數：{m.losing_trades:>6d} 筆",
        f"🎯 勝率：    {m.win_rate:>9.1f} %",
        f"📊 平均報酬：{m.avg_return:>9.2f} %",
        f"📊 夏普比率：{m.sharpe_ratio:>9.2f}",
        f"📊 獲利因子：{trade_metrics['profit_factor']:>9.2f}",
        f"📅 平均持有：{m.avg_holding_days:>7.1f} 天",
        f"📅 最長持有：{m.max_holding_days:>7d} 天",
        "=" * 50,
    ]

    return "\n".join(lines)
