"""
台股布林通道交易訊號系統 - 資料匯出模組

將交易紀錄匯出為 CSV 檔案或字典列表（供 JSON API 使用）。
"""

import csv
import logging
from pathlib import Path
from typing import Optional

from backend.data.models import TradeRecord
from backend.trade_journal.journal import trade_to_dict

logger = logging.getLogger(__name__)


def export_to_csv(trades: list[TradeRecord], filepath: str) -> str:
    """
    將交易紀錄匯出為 CSV 檔案

    Parameters
    ----------
    trades : list[TradeRecord]
        交易紀錄列表
    filepath : str
        輸出檔案路徑

    Returns
    -------
    str
        實際寫入的檔案路徑
    """
    if not trades:
        logger.warning("沒有交易紀錄可匯出")
        return filepath

    # 確保目錄存在
    output_path = Path(filepath)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # CSV 欄位定義
    fieldnames = [
        "id",
        "stock_id",
        "stock_name",
        "buy_price",
        "buy_time",
        "buy_shares",
        "sell_price",
        "sell_time",
        "signal_source",
        "status",
        "profit_loss",
        "return_pct",
        "holding_days",
        "note",
    ]

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")

        # 寫入中文欄位名稱作為標題
        header_map = {
            "id": "編號",
            "stock_id": "股票代號",
            "stock_name": "股票名稱",
            "buy_price": "買入價格",
            "buy_time": "買入時間",
            "buy_shares": "買入股數",
            "sell_price": "賣出價格",
            "sell_time": "賣出時間",
            "signal_source": "訊號來源",
            "status": "狀態",
            "profit_loss": "損益(元)",
            "return_pct": "報酬率(%)",
            "holding_days": "持有天數",
            "note": "備註",
        }
        writer.writerow(header_map)

        # 寫入資料
        for trade in trades:
            row = {
                "id": trade.id,
                "stock_id": trade.stock_id,
                "stock_name": trade.stock_name or "",
                "buy_price": trade.buy_price,
                "buy_time": trade.buy_time.strftime("%Y-%m-%d %H:%M") if trade.buy_time else "",
                "buy_shares": trade.buy_shares,
                "sell_price": trade.sell_price if trade.sell_price else "",
                "sell_time": trade.sell_time.strftime("%Y-%m-%d %H:%M") if trade.sell_time else "",
                "signal_source": trade.signal_source,
                "status": trade.status,
                "profit_loss": trade.profit_loss if trade.profit_loss is not None else "",
                "return_pct": trade.return_pct if trade.return_pct is not None else "",
                "holding_days": trade.holding_days if trade.holding_days is not None else "",
                "note": trade.note or "",
            }
            writer.writerow(row)

    logger.info(f"已匯出 {len(trades)} 筆交易紀錄至 {output_path}")
    return str(output_path)


def export_to_dict(trades: list[TradeRecord]) -> list[dict]:
    """
    將交易紀錄列表轉為字典列表（供 JSON API 回傳）

    Parameters
    ----------
    trades : list[TradeRecord]
        交易紀錄列表

    Returns
    -------
    list[dict]
        序列化後的字典列表
    """
    return [trade_to_dict(t) for t in trades]


def export_to_excel(trades: list[TradeRecord], filepath: str) -> str:
    """
    將交易紀錄匯出為 Excel 檔案

    Parameters
    ----------
    trades : list[TradeRecord]
        交易紀錄列表
    filepath : str
        輸出檔案路徑（.xlsx）

    Returns
    -------
    str
        實際寫入的檔案路徑
    """
    import pandas as pd

    if not trades:
        logger.warning("沒有交易紀錄可匯出")
        return filepath

    output_path = Path(filepath)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 轉為 DataFrame
    data = export_to_dict(trades)
    df = pd.DataFrame(data)

    # 重新命名欄位為中文
    column_map = {
        "id": "編號",
        "stock_id": "股票代號",
        "stock_name": "股票名稱",
        "buy_price": "買入價格",
        "buy_time": "買入時間",
        "buy_shares": "買入股數",
        "sell_price": "賣出價格",
        "sell_time": "賣出時間",
        "signal_source": "訊號來源",
        "status": "狀態",
        "profit_loss": "損益(元)",
        "return_pct": "報酬率(%)",
        "holding_days": "持有天數",
        "note": "備註",
    }

    # 只重新命名存在的欄位
    rename_cols = {k: v for k, v in column_map.items() if k in df.columns}
    df = df.rename(columns=rename_cols)

    # 移除不需要的欄位
    drop_cols = ["created_at", "updated_at"]
    df = df.drop(columns=[c for c in drop_cols if c in df.columns], errors="ignore")

    df.to_excel(str(output_path), index=False, engine="openpyxl")

    logger.info(f"已匯出 {len(trades)} 筆交易紀錄至 {output_path}")
    return str(output_path)
