"""
台股布林通道交易訊號系統 - FastAPI 主應用程式

提供完整的 RESTful API，包含：
- 股票資料與指標查詢
- 交易訊號偵測
- 市場篩選
- 回測功能
- 交易日誌 CRUD
- 投資組合統計
- 資料匯出
"""

import json
import logging
import tempfile
from datetime import date, datetime
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.config import (
    BB_PERIOD, BB_STD, MA_PERIOD, CONSECUTIVE_K_THRESHOLD,
    DEFAULT_INITIAL_CAPITAL, PROJECT_DIR,
)
from backend.data.database import create_all_tables, get_db
from backend.data.fetcher import fetch_stock_data, get_all_twse_stock_ids
from backend.data.models import BacktestResult, Signal
from backend.strategy.signal_detector import (
    detect_all_signals,
    prepare_dataframe_with_indicators,
)
from backend.strategy.screener import screen_stocks
from backend.backtest.engine import run_backtest, backtest_result_to_db_dict
from backend.backtest.report import generate_report, format_report_text
from backend.trade_journal.journal import (
    create_trade, update_trade, delete_trade,
    get_trade, get_all_trades, trade_to_dict,
)
from backend.trade_journal.statistics import (
    calculate_portfolio_stats, get_equity_curve,
    get_monthly_returns, get_stock_breakdown,
)
from backend.trade_journal.export import export_to_csv, export_to_dict

# ============================================================
# 日誌設定
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ============================================================
# FastAPI 應用程式
# ============================================================
app = FastAPI(
    title="台股布林通道交易訊號系統",
    description=(
        "基於布林通道策略的台股交易訊號偵測、回測與交易日誌管理系統。\n\n"
        "**台灣慣例**：紅 K = 陽線（看漲），綠 K = 陰線（看跌）\n"
        "**股票代號**：XXXX.TW（上市）/ XXXX.TWO（上櫃）\n"
        "**1 張 = 1000 股**"
    ),
    version="1.0.0",
)

# CORS 設定（開發環境允許所有來源）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# 前端靜態檔案（在路由定義前先掛載）
# ============================================================
import pathlib as _pathlib
_frontend_dir = _pathlib.Path(__file__).resolve().parent.parent / "frontend"
if _frontend_dir.exists():
    app.mount("/app", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")


# ============================================================
# Pydantic 請求/回應模型
# ============================================================
class BacktestRequest(BaseModel):
    """回測請求"""
    stock_id: str = Field(..., description="股票代號，例如 2330")
    start_date: str = Field(..., description="起始日期 YYYY-MM-DD")
    end_date: str = Field(..., description="結束日期 YYYY-MM-DD")
    initial_capital: float = Field(
        default=DEFAULT_INITIAL_CAPITAL, description="初始資金（新台幣）"
    )
    bb_period: int = Field(default=BB_PERIOD, description="布林通道週期")
    bb_std: float = Field(default=BB_STD, description="布林通道標準差倍數")
    ma_period: int = Field(default=MA_PERIOD, description="均線週期")
    consecutive_k: int = Field(
        default=CONSECUTIVE_K_THRESHOLD, description="連續 K 棒門檻"
    )


class TradeCreateRequest(BaseModel):
    """新增交易請求"""
    stock_id: str = Field(..., description="股票代號")
    stock_name: Optional[str] = Field(None, description="股票名稱")
    buy_price: float = Field(..., description="買入價格")
    buy_time: str = Field(..., description="買入時間 ISO 格式")
    buy_shares: int = Field(..., description="買入股數")
    sell_price: Optional[float] = Field(None, description="賣出價格")
    sell_time: Optional[str] = Field(None, description="賣出時間")
    note: Optional[str] = Field(None, description="備註")
    signal_source: str = Field(default="MANUAL", description="訊號來源 SYSTEM/MANUAL")
    status: str = Field(default="HOLDING", description="狀態 HOLDING/CLOSED/STOPLOSS")


class TradeUpdateRequest(BaseModel):
    """更新交易請求"""
    stock_id: Optional[str] = None
    stock_name: Optional[str] = None
    buy_price: Optional[float] = None
    buy_time: Optional[str] = None
    buy_shares: Optional[int] = None
    sell_price: Optional[float] = None
    sell_time: Optional[str] = None
    note: Optional[str] = None
    signal_source: Optional[str] = None
    status: Optional[str] = None


# ============================================================
# 啟動事件：建立資料表
# ============================================================
@app.on_event("startup")
async def startup_event():
    """應用程式啟動時建立資料庫表格"""
    logger.info("正在初始化資料庫...")
    create_all_tables()
    logger.info("資料庫初始化完成")


# ============================================================
# 健康檢查
# ============================================================
@app.get("/", tags=["系統"])
async def root():
    """重導至前端介面"""
    return RedirectResponse(url="/app/")


@app.get("/health", tags=["系統"])
async def health_check():
    """健康檢查端點"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


# ============================================================
# 股票資料 API
# ============================================================
@app.get("/api/stock/{stock_id}/data", tags=["股票資料"])
async def get_stock_data(
    stock_id: str,
    period: str = Query(default="6mo", description="資料期間：1mo/3mo/6mo/1y/2y"),
    start: Optional[str] = Query(default=None, description="起始日期 YYYY-MM-DD"),
    end: Optional[str] = Query(default=None, description="結束日期 YYYY-MM-DD"),
):
    """
    取得股票 OHLCV 資料及技術指標

    回傳包含布林通道、均線、帶寬、趨勢判斷的完整資料。
    """
    try:
        df = fetch_stock_data(stock_id, period=period, start=start, end=end)
        if df.empty:
            raise HTTPException(
                status_code=404,
                detail=f"找不到 {stock_id} 的股價資料"
            )

        # 計算所有指標
        df = prepare_dataframe_with_indicators(df)

        # 轉為 JSON 格式，確保 NaN/Inf 轉為 None
        records = df.copy()
        records["date"] = records["date"].astype(str)

        # 強制清除所有 NaN / Inf，轉為 None（相容 pandas 3.x）
        import math

        def clean_value(v):
            if v is None:
                return None
            try:
                f = float(v)
                if math.isnan(f) or math.isinf(f):
                    return None
                return f
            except (TypeError, ValueError):
                return v

        raw_records = records.to_dict(orient="records")
        cleaned = [
            {k: clean_value(val) for k, val in row.items()}
            for row in raw_records
        ]

        return {
            "stock_id": stock_id,
            "count": len(cleaned),
            "data": cleaned,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取得 {stock_id} 資料時發生錯誤: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# 訊號 API
# ============================================================
@app.get("/api/stock/{stock_id}/signals", tags=["交易訊號"])
async def get_stock_signals(
    stock_id: str,
    period: str = Query(default="6mo", description="資料期間"),
    consecutive_k: int = Query(
        default=CONSECUTIVE_K_THRESHOLD, description="連續 K 棒門檻"
    ),
):
    """
    取得指定股票的交易訊號

    依據布林通道策略偵測買進與賣出訊號。
    """
    try:
        df = fetch_stock_data(stock_id, period=period)
        if df.empty:
            raise HTTPException(
                status_code=404,
                detail=f"找不到 {stock_id} 的股價資料"
            )

        signals = detect_all_signals(df, consecutive_k=consecutive_k)

        return {
            "stock_id": stock_id,
            "signal_count": len(signals),
            "signals": [
                {
                    "date": s.date.isoformat(),
                    "signal_type": s.signal_type,
                    "price": s.price,
                    "trend_direction": s.trend_direction,
                    "details": s.details,
                }
                for s in signals
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"偵測 {stock_id} 訊號時發生錯誤: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# 市場篩選 API
# ============================================================
@app.get("/api/screener", tags=["市場篩選"])
async def run_screener(
    stock_ids: Optional[str] = Query(
        default=None,
        description="股票代號（逗號分隔），留空則掃描全部主要上市股票",
    ),
    lookback_days: int = Query(default=5, description="只顯示最近 N 天內的訊號"),
):
    """
    市場篩選 - 掃描多檔股票找出活躍訊號

    注意：掃描全部股票可能需要較長時間。
    """
    try:
        ids = None
        if stock_ids:
            ids = [s.strip() for s in stock_ids.split(",") if s.strip()]

        results = screen_stocks(stock_ids=ids, lookback_days=lookback_days)

        return {
            "scanned_count": len(ids) if ids else len(get_all_twse_stock_ids()),
            "signal_count": len(results),
            "results": [
                {
                    "stock_id": r.stock_id,
                    "signal_type": r.signal_type,
                    "trend": r.trend,
                    "price": r.price,
                    "signal_date": r.signal_date.isoformat(),
                    "details": r.details,
                }
                for r in results
            ],
        }

    except Exception as e:
        logger.error(f"市場篩選時發生錯誤: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# 回測 API
# ============================================================
@app.post("/api/backtest", tags=["回測"])
async def run_backtest_api(
    request: BacktestRequest,
    db: Session = Depends(get_db),
):
    """
    執行回測

    使用布林通道策略對指定股票進行歷史回測，計算績效指標。
    """
    try:
        output = run_backtest(
            stock_id=request.stock_id,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_capital=request.initial_capital,
            bb_period=request.bb_period,
            bb_std=request.bb_std,
            ma_period=request.ma_period,
            consecutive_k=request.consecutive_k,
        )

        # 將結果存入資料庫
        db_data = backtest_result_to_db_dict(output)
        db_record = BacktestResult(**db_data)
        db.add(db_record)
        db.commit()
        db.refresh(db_record)

        # 產生報告
        report = generate_report(output)
        report["backtest_id"] = db_record.id

        return report

    except Exception as e:
        logger.error(f"回測 {request.stock_id} 時發生錯誤: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/backtest/{stock_id}", tags=["回測"])
async def get_backtest_results(
    stock_id: str,
    db: Session = Depends(get_db),
    limit: int = Query(default=10, description="回傳筆數上限"),
):
    """
    取得指定股票的歷史回測結果
    """
    results = (
        db.query(BacktestResult)
        .filter(BacktestResult.stock_id == stock_id)
        .order_by(BacktestResult.created_at.desc())
        .limit(limit)
        .all()
    )

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"找不到 {stock_id} 的回測結果"
        )

    return {
        "stock_id": stock_id,
        "count": len(results),
        "results": [
            {
                "id": r.id,
                "start_date": r.start_date.isoformat(),
                "end_date": r.end_date.isoformat(),
                "params": json.loads(r.params_json) if r.params_json else {},
                "total_trades": r.total_trades,
                "win_rate": r.win_rate,
                "total_return": r.total_return,
                "max_drawdown": r.max_drawdown,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "details": json.loads(r.results_json) if r.results_json else {},
            }
            for r in results
        ],
    }


# ============================================================
# 交易日誌 API
# ============================================================
@app.post("/api/journal", tags=["交易日誌"])
async def create_trade_api(
    request: TradeCreateRequest,
    db: Session = Depends(get_db),
):
    """新增交易紀錄"""
    try:
        trade = create_trade(db, request.model_dump())
        return {
            "message": "交易紀錄建立成功",
            "trade": trade_to_dict(trade),
        }
    except Exception as e:
        logger.error(f"新增交易紀錄失敗: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/journal", tags=["交易日誌"])
async def list_trades_api(
    stock_id: Optional[str] = Query(default=None, description="篩選股票代號"),
    status: Optional[str] = Query(default=None, description="篩選狀態"),
    signal_source: Optional[str] = Query(default=None, description="篩選訊號來源"),
    limit: int = Query(default=100, description="回傳筆數上限"),
    offset: int = Query(default=0, description="分頁偏移量"),
    db: Session = Depends(get_db),
):
    """查詢交易紀錄列表"""
    trades = get_all_trades(
        db,
        stock_id=stock_id,
        status=status,
        signal_source=signal_source,
        limit=limit,
        offset=offset,
    )
    return {
        "count": len(trades),
        "trades": [trade_to_dict(t) for t in trades],
    }


@app.get("/api/journal/{trade_id}", tags=["交易日誌"])
async def get_trade_api(
    trade_id: int,
    db: Session = Depends(get_db),
):
    """取得單筆交易紀錄"""
    trade = get_trade(db, trade_id)
    if trade is None:
        raise HTTPException(status_code=404, detail=f"找不到交易紀錄 #{trade_id}")
    return trade_to_dict(trade)


@app.put("/api/journal/{trade_id}", tags=["交易日誌"])
async def update_trade_api(
    trade_id: int,
    request: TradeUpdateRequest,
    db: Session = Depends(get_db),
):
    """
    更新交易紀錄

    填入 sell_price 和 sell_time 後會自動計算損益與報酬率。
    """
    # 只傳送有值的欄位
    update_data = {k: v for k, v in request.model_dump().items() if v is not None}

    if not update_data:
        raise HTTPException(status_code=400, detail="沒有提供要更新的欄位")

    trade = update_trade(db, trade_id, update_data)
    if trade is None:
        raise HTTPException(status_code=404, detail=f"找不到交易紀錄 #{trade_id}")

    return {
        "message": "交易紀錄更新成功",
        "trade": trade_to_dict(trade),
    }


@app.delete("/api/journal/{trade_id}", tags=["交易日誌"])
async def delete_trade_api(
    trade_id: int,
    db: Session = Depends(get_db),
):
    """刪除交易紀錄"""
    success = delete_trade(db, trade_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"找不到交易紀錄 #{trade_id}")
    return {"message": f"交易紀錄 #{trade_id} 已刪除"}


# ============================================================
# 投資組合統計 API
# ============================================================
@app.get("/api/journal/stats", tags=["投資組合統計"])
async def get_portfolio_stats(
    db: Session = Depends(get_db),
):
    """取得投資組合整體統計"""
    trades = get_all_trades(db, limit=10000)
    stats = calculate_portfolio_stats(trades)
    equity = get_equity_curve(trades)
    monthly = get_monthly_returns(trades)
    breakdown = get_stock_breakdown(trades)

    return {
        "statistics": stats,
        "equity_curve": equity,
        "monthly_returns": monthly,
        "stock_breakdown": breakdown,
    }


# ============================================================
# 匯出 API
# ============================================================
@app.get("/api/journal/export", tags=["資料匯出"])
async def export_trades(
    format: str = Query(default="json", description="匯出格式：json / csv"),
    stock_id: Optional[str] = Query(default=None, description="篩選股票代號"),
    status: Optional[str] = Query(default=None, description="篩選狀態"),
    db: Session = Depends(get_db),
):
    """
    匯出交易紀錄

    支援 JSON 和 CSV 格式。CSV 格式會回傳檔案下載。
    """
    trades = get_all_trades(db, stock_id=stock_id, status=status, limit=10000)

    if format.lower() == "csv":
        export_dir = PROJECT_DIR / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        filename = f"trades_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = str(export_dir / filename)
        export_to_csv(trades, filepath)
        return FileResponse(
            filepath,
            media_type="text/csv",
            filename=filename,
        )
    else:
        return {
            "count": len(trades),
            "trades": export_to_dict(trades),
        }


# ============================================================
# 主要股票清單 API
# ============================================================
@app.get("/api/stocks", tags=["股票資料"])
async def get_stock_list():
    """取得主要上市股票代號清單"""
    stocks = get_all_twse_stock_ids()
    return {
        "count": len(stocks),
        "stocks": stocks,
    }


# ============================================================
# 啟動入口
# ============================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
