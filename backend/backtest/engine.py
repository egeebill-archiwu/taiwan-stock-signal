"""
台股布林通道交易訊號系統 - 回測引擎

模擬布林通道策略的歷史表現，追蹤投資組合價值與交易紀錄。
每次買進以整張（1000 股）為單位。
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from typing import Optional

import pandas as pd

from backend.config import (
    DEFAULT_INITIAL_CAPITAL,
    SHARES_PER_LOT,
    BB_PERIOD,
    BB_STD,
    MA_PERIOD,
    CONSECUTIVE_K_THRESHOLD,
    TREND_LOOKBACK,
)
from backend.data.fetcher import fetch_stock_data
from backend.strategy.signal_detector import detect_all_signals, SignalResult

logger = logging.getLogger(__name__)


@dataclass
class BacktestTrade:
    """回測中的單筆交易"""
    stock_id: str
    buy_date: str
    buy_price: float
    buy_shares: int
    sell_date: Optional[str] = None
    sell_price: Optional[float] = None
    profit_loss: Optional[float] = None
    return_pct: Optional[float] = None
    holding_days: Optional[int] = None


@dataclass
class BacktestMetrics:
    """回測績效指標"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    total_return: float = 0.0
    avg_return: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    initial_capital: float = 0.0
    final_capital: float = 0.0
    max_holding_days: int = 0
    avg_holding_days: float = 0.0


@dataclass
class BacktestOutput:
    """回測結果"""
    stock_id: str
    start_date: str
    end_date: str
    params: dict
    metrics: BacktestMetrics
    trades: list[BacktestTrade] = field(default_factory=list)
    equity_curve: list[dict] = field(default_factory=list)


def run_backtest(
    stock_id: str,
    start_date: str,
    end_date: str,
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
    bb_period: int = BB_PERIOD,
    bb_std: float = BB_STD,
    ma_period: int = MA_PERIOD,
    consecutive_k: int = CONSECUTIVE_K_THRESHOLD,
) -> BacktestOutput:
    """
    執行回測

    根據布林通道策略，模擬歷史買賣操作。
    每次買進以整張（1000 股）為單位，使用可用資金的 100%。

    Parameters
    ----------
    stock_id : str
        股票代號
    start_date : str
        回測起始日期（格式 YYYY-MM-DD）
    end_date : str
        回測結束日期（格式 YYYY-MM-DD）
    initial_capital : float
        初始資金（新台幣）
    bb_period : int
        布林通道週期
    bb_std : float
        布林通道標準差倍數
    ma_period : int
        均線週期
    consecutive_k : int
        連續 K 棒門檻

    Returns
    -------
    BacktestOutput
        回測結果，包含績效指標、交易紀錄、權益曲線
    """
    logger.info(
        f"開始回測 {stock_id}，期間 {start_date} ~ {end_date}，"
        f"初始資金 {initial_capital:,.0f}"
    )

    params = {
        "bb_period": bb_period,
        "bb_std": bb_std,
        "ma_period": ma_period,
        "consecutive_k": consecutive_k,
        "initial_capital": initial_capital,
    }

    # 取得歷史資料（多抓一些資料讓指標有足夠的預熱期）
    df = fetch_stock_data(stock_id, start=start_date, end=end_date)

    if df.empty:
        logger.warning(f"無法取得 {stock_id} 的歷史資料")
        return BacktestOutput(
            stock_id=stock_id,
            start_date=start_date,
            end_date=end_date,
            params=params,
            metrics=BacktestMetrics(initial_capital=initial_capital, final_capital=initial_capital),
        )

    # 偵測所有訊號
    signals = detect_all_signals(df, consecutive_k=consecutive_k, ma_period=ma_period)

    # 模擬交易
    cash = initial_capital
    position: Optional[BacktestTrade] = None
    completed_trades: list[BacktestTrade] = []
    equity_curve: list[dict] = []

    # 將訊號轉為字典以便快速查詢
    signal_map: dict[str, SignalResult] = {}
    for sig in signals:
        date_str = sig.date.isoformat() if isinstance(sig.date, date) else str(sig.date)
        key = f"{date_str}_{sig.signal_type}"
        signal_map[key] = sig

    # 逐日模擬
    for i in range(len(df)):
        row = df.iloc[i]
        current_date = row["date"]
        if isinstance(current_date, pd.Timestamp):
            current_date = current_date.date()
        date_str = current_date.isoformat()

        # 計算當日組合價值
        if position is not None:
            portfolio_value = cash + position.buy_shares * row["close"]
        else:
            portfolio_value = cash

        equity_curve.append({
            "date": date_str,
            "portfolio_value": round(portfolio_value, 2),
            "cash": round(cash, 2),
            "position_value": round(portfolio_value - cash, 2),
        })

        # 檢查賣出訊號（優先處理，先賣後買）
        sell_key = f"{date_str}_SELL"
        if sell_key in signal_map and position is not None:
            sell_price = row["close"]
            sell_amount = position.buy_shares * sell_price

            # 計算損益
            buy_amount = position.buy_shares * position.buy_price
            profit_loss = sell_amount - buy_amount
            return_pct = (profit_loss / buy_amount) * 100 if buy_amount > 0 else 0.0

            buy_dt = datetime.fromisoformat(position.buy_date)
            holding_days = (current_date - buy_dt.date()).days if isinstance(buy_dt, datetime) else 0

            position.sell_date = date_str
            position.sell_price = sell_price
            position.profit_loss = round(profit_loss, 2)
            position.return_pct = round(return_pct, 2)
            position.holding_days = holding_days

            cash += sell_amount
            completed_trades.append(position)
            position = None

            logger.info(
                f"回測賣出 {stock_id} @ {sell_price:.2f}，損益 {profit_loss:,.0f}"
            )

        # 檢查買進訊號
        buy_key = f"{date_str}_BUY"
        if buy_key in signal_map and position is None:
            buy_price = row["close"]
            # 計算可買張數（整張為單位）
            lots = int(cash / (buy_price * SHARES_PER_LOT))
            if lots > 0:
                buy_shares = lots * SHARES_PER_LOT
                cost = buy_shares * buy_price
                cash -= cost

                position = BacktestTrade(
                    stock_id=stock_id,
                    buy_date=date_str,
                    buy_price=buy_price,
                    buy_shares=buy_shares,
                )

                logger.info(
                    f"回測買進 {stock_id} @ {buy_price:.2f}，{lots} 張 ({buy_shares} 股)"
                )

    # 如果回測結束時仍有持倉，以最後收盤價結算
    if position is not None and not df.empty:
        last_row = df.iloc[-1]
        last_date = last_row["date"]
        if isinstance(last_date, pd.Timestamp):
            last_date = last_date.date()

        sell_price = last_row["close"]
        sell_amount = position.buy_shares * sell_price
        buy_amount = position.buy_shares * position.buy_price
        profit_loss = sell_amount - buy_amount
        return_pct = (profit_loss / buy_amount) * 100 if buy_amount > 0 else 0.0

        buy_dt = datetime.fromisoformat(position.buy_date)
        holding_days = (last_date - buy_dt.date()).days if isinstance(buy_dt, datetime) else 0

        position.sell_date = last_date.isoformat()
        position.sell_price = sell_price
        position.profit_loss = round(profit_loss, 2)
        position.return_pct = round(return_pct, 2)
        position.holding_days = holding_days

        cash += sell_amount
        completed_trades.append(position)

    # 計算績效指標
    metrics = _calculate_backtest_metrics(completed_trades, initial_capital, cash, equity_curve)

    output = BacktestOutput(
        stock_id=stock_id,
        start_date=start_date,
        end_date=end_date,
        params=params,
        metrics=metrics,
        trades=completed_trades,
        equity_curve=equity_curve,
    )

    logger.info(
        f"回測完成 {stock_id}：{metrics.total_trades} 筆交易，"
        f"總報酬 {metrics.total_return:.2f}%，勝率 {metrics.win_rate:.1f}%"
    )

    return output


def _calculate_backtest_metrics(
    trades: list[BacktestTrade],
    initial_capital: float,
    final_capital: float,
    equity_curve: list[dict],
) -> BacktestMetrics:
    """
    計算回測績效指標

    Parameters
    ----------
    trades : list[BacktestTrade]
        已完成的交易列表
    initial_capital : float
        初始資金
    final_capital : float
        最終資金
    equity_curve : list[dict]
        權益曲線

    Returns
    -------
    BacktestMetrics
        績效指標
    """
    metrics = BacktestMetrics(
        initial_capital=initial_capital,
        final_capital=round(final_capital, 2),
    )

    if not trades:
        return metrics

    metrics.total_trades = len(trades)

    # 勝率
    winning = [t for t in trades if t.profit_loss is not None and t.profit_loss > 0]
    losing = [t for t in trades if t.profit_loss is not None and t.profit_loss <= 0]
    metrics.winning_trades = len(winning)
    metrics.losing_trades = len(losing)
    metrics.win_rate = round(len(winning) / len(trades) * 100, 2) if trades else 0.0

    # 總報酬率
    metrics.total_return = round(
        (final_capital - initial_capital) / initial_capital * 100, 2
    )

    # 平均報酬率
    returns = [t.return_pct for t in trades if t.return_pct is not None]
    metrics.avg_return = round(sum(returns) / len(returns), 2) if returns else 0.0

    # 持有天數
    hold_days = [t.holding_days for t in trades if t.holding_days is not None]
    if hold_days:
        metrics.max_holding_days = max(hold_days)
        metrics.avg_holding_days = round(sum(hold_days) / len(hold_days), 1)

    # 最大回撤
    if equity_curve:
        values = [p["portfolio_value"] for p in equity_curve]
        peak = values[0]
        max_dd = 0.0
        for v in values:
            if v > peak:
                peak = v
            dd = (peak - v) / peak * 100 if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd
        metrics.max_drawdown = round(max_dd, 2)

    # 夏普比率（年化，以日報酬率計算）
    if len(equity_curve) > 1:
        values = [p["portfolio_value"] for p in equity_curve]
        daily_returns = []
        for i in range(1, len(values)):
            if values[i - 1] > 0:
                daily_returns.append((values[i] - values[i - 1]) / values[i - 1])

        if daily_returns:
            import numpy as np
            avg_daily = np.mean(daily_returns)
            std_daily = np.std(daily_returns)
            if std_daily > 0:
                # 台股一年約 250 個交易日
                metrics.sharpe_ratio = round(
                    (avg_daily / std_daily) * (250 ** 0.5), 2
                )

    return metrics


def backtest_result_to_db_dict(output: BacktestOutput) -> dict:
    """
    將回測結果轉換為可存入資料庫的字典格式

    Returns
    -------
    dict
        對應 BacktestResult 資料表欄位的字典
    """
    return {
        "stock_id": output.stock_id,
        "start_date": output.start_date,
        "end_date": output.end_date,
        "params_json": json.dumps(output.params, ensure_ascii=False),
        "total_trades": output.metrics.total_trades,
        "win_rate": output.metrics.win_rate,
        "total_return": output.metrics.total_return,
        "max_drawdown": output.metrics.max_drawdown,
        "results_json": json.dumps(
            {
                "trades": [asdict(t) for t in output.trades],
                "equity_curve": output.equity_curve,
                "metrics": asdict(output.metrics),
            },
            ensure_ascii=False,
        ),
    }
