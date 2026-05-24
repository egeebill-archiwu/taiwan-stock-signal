"""
台股布林通道交易訊號系統 - 市場篩選模組

批次掃描多檔股票，找出目前有買賣訊號的標的。
採用 ThreadPoolExecutor 進行多執行緒並行下載以加速掃描，並實作記憶體快取。
"""

import time
import logging
import concurrent.futures
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional
import pandas as pd

from backend.data.fetcher import fetch_stock_data, get_all_twse_stock_ids, get_stock_name, _to_yahoo_ticker
from backend.strategy.signal_detector import detect_all_signals

logger = logging.getLogger(__name__)

# 台灣市值前 100 大上市公司名稱對照表
STOCK_NAMES = {
    "2330": "台積電", "2303": "聯電", "2454": "聯發科", "3711": "日月光投控",
    "2379": "瑞昱", "3034": "聯詠", "6415": "矽力-KY", "3529": "力旺",
    "2408": "南亞科", "3443": "創意", "2317": "鴻海", "2382": "廣達",
    "2356": "英業達", "2353": "宏碁", "3231": "緯創", "2301": "光寶科",
    "2357": "華碩", "4938": "和碩", "3017": "奇鋐", "2345": "智邦",
    "2881": "富邦金", "2882": "國泰金", "2891": "中信金", "2886": "兆豐金",
    "2884": "玉山金", "2885": "元大金", "2887": "台新金", "2890": "永豐金",
    "2880": "華南金", "2883": "開發金", "2892": "第一金", "5880": "合庫金",
    "2888": "新光金", "2324": "仁寶", "5876": "上海商銀", "2889": "國票金", "2002": "中鋼",
    "1301": "台塑", "1303": "南亞", "1326": "台化", "6505": "台塑化",
    "1101": "台泥", "1102": "亞泥", "1216": "統一", "2912": "統一超",
    "1476": "儒鴻", "9910": "豐泰", "2207": "和泰車", "9921": "巨大",
    "1590": "亞德客-KY", "2201": "裕隆", "2412": "中華電", "3045": "台灣大",
    "4904": "遠傳", "2603": "長榮", "2609": "陽明", "2615": "萬海",
    "2610": "華航", "2618": "長榮航", "2006": "東和鋼鐵", "2014": "中鴻",
    "1312": "國喬", "1304": "台聚", "2409": "友達", "3481": "群創",
    "2474": "可成", "3008": "大立光", "6269": "台郡", "2327": "國巨",
    "3037": "欣興", "4958": "臻鼎-KY", "8046": "南電", "2492": "華新科",
    "2377": "微星", "3702": "大聯大", "6488": "環球晶", "5347": "世界",
    "2404": "漢唐", "1227": "佳格", "4743": "合一", "6446": "藥華藥",
    "1795": "美時", "2504": "國產", "2542": "興富發", "5534": "長虹",
    "2545": "皇翔", "1402": "遠東新", "2105": "正新", "2308": "台達電",
    "3661": "世芯-KY", "2395": "研華", "6409": "旭隼", "2049": "上銀",
    "8069": "元太", "1504": "東元", "2376": "技嘉", "6239": "力成",
    "5871": "中租-KY", "6756": "威鋒電子", "3653": "健策", "6547": "高端疫苗",
    "2383": "台光電"
}

@dataclass
class ScreenerResult:
    """篩選結果"""
    stock_id: str
    stock_name: str
    signal_type: str       # "BUY" 或 "SELL"
    trend: str             # 趨勢方向
    price: float           # 觸發價格
    signal_date: date      # 訊號日期
    change: float          # 訊號日漲跌幅
    details: str = ""      # 詳細描述

# 記憶體快取結構
_screener_cache = {
    "timestamp": 0.0,
    "results": None,
    "lookback_days": None,
    "period": None,
    "strategy": None
}
CACHE_DURATION = 300  # 快取時效為 5 分鐘 (300 秒)


def _process_single_stock_df(sid: str, df: pd.DataFrame, cutoff_date: date, strategy: str = "bb") -> list[ScreenerResult]:
    """從已整理好的 DataFrame 分析訊號的輔助函式"""
    try:
        if df.empty:
            return []

        # 根據不同策略偵測訊號
        if strategy == "ma_conv":
            from backend.strategy.ma_convergence import detect_ma_signals
            if len(df) < 65:
                return []
            signals = detect_ma_signals(df)
        else:
            if len(df) < 25:
                return []
            signals = detect_all_signals(df)

        # 篩選出大於等於截止日期的訊號
        recent_signals = [s for s in signals if s.date >= cutoff_date]

        results = []
        for signal in recent_signals:
            # 計算該訊號日期的漲跌幅
            change_val = 0.0
            try:
                sig_ts = pd.to_datetime(signal.date).normalize()
                matching_rows = df[df["date"] == sig_ts]
                if not matching_rows.empty:
                    idx = matching_rows.index[0]
                    if idx > 0:
                        prev_close = df.iloc[idx - 1]["close"]
                        close = df.iloc[idx]["close"]
                        change_val = round(((close - prev_close) / prev_close) * 100, 2)
            except Exception as ex:
                logger.warning(f"計算 {sid} 在 {signal.date} 的漲跌幅時發生錯誤: {ex}")

            stock_name = get_stock_name(sid)
            results.append(ScreenerResult(
                stock_id=signal.stock_id,
                stock_name=stock_name,
                signal_type=signal.signal_type,
                trend=signal.trend_direction,
                price=signal.price,
                signal_date=signal.date,
                change=change_val,
                details=signal.details,
            ))
        return results

    except Exception as e:
        logger.error(f"分析 {sid} 訊號時發生錯誤: {e}")
        return []


def _screen_single_stock(sid: str, period: str, cutoff_date: date, strategy: str = "bb") -> list[ScreenerResult]:
    """掃描單一股票的輔助函式（供 ThreadPool 呼叫）"""
    try:
        df = fetch_stock_data(sid, period=period)
        return _process_single_stock_df(sid, df, cutoff_date, strategy)
    except Exception as e:
        logger.error(f"掃描 {sid} 時發生錯誤: {e}")
        return []


def screen_stocks(
    stock_ids: Optional[list[str]] = None,
    period: str = "6mo",
    lookback_days: int = 5,
    force_refresh: bool = False,
    strategy: str = "bb",
) -> list[ScreenerResult]:
    """
    掃描市場，找出有活躍訊號的股票（支援多執行緒與快取）

    Parameters
    ----------
    stock_ids : list[str], optional
        要掃描的股票代號清單，若為 None 則使用全部主要上市股票
    period : str
        資料擷取期間
    lookback_days : int
        只回傳最近 N 個交易日內的訊號
    force_refresh : bool
        是否強制重新整理（繞過快取）

    Returns
    -------
    list[ScreenerResult]
        篩選結果列表，按訊號日期降冪排序
    """
    global _screener_cache

    current_time = time.time()
    if (not force_refresh and 
        stock_ids is None and 
        _screener_cache["results"] is not None and 
        (current_time - _screener_cache["timestamp"]) < CACHE_DURATION and
        _screener_cache["lookback_days"] == lookback_days and
        _screener_cache["period"] == period and
        _screener_cache["strategy"] == strategy):
        logger.info(f"使用選股快取資料 (快取時間: {current_time - _screener_cache['timestamp']:.1f} 秒前)")
        return _screener_cache["results"]

    if stock_ids is None:
        stock_ids = get_all_twse_stock_ids()

    results: list[ScreenerResult] = []
    cutoff_date = date.today() - timedelta(days=lookback_days)
    total = len(stock_ids)

    logger.info(f"開始批次下載與篩選市場... 總共 {total} 檔股票")
    t_start = time.time()

    # 取得 Yahoo Tickers
    tickers = [_to_yahoo_ticker(sid) for sid in stock_ids]

    # 執行批次下載
    import yfinance as yf
    try:
        df_all = yf.download(tickers, period=period, group_by="ticker", auto_adjust=True, threads=True, progress=False)
        logger.info(f"yfinance 批次下載完成，耗時: {time.time() - t_start:.2f} 秒")
        # 檢查是否下載到空資料或全 NaN 資料 (例如在 Render 上遭 Yahoo Finance 阻擋)
        if df_all.empty or df_all.dropna(how="all").empty or (hasattr(df_all, "columns") and len(df_all.columns) == 0):
            raise ValueError("yf.download 回傳空資料或所有數值皆為 NaN (可能遭 Yahoo 阻擋)")
    except Exception as e:
        logger.error(f"yfinance 批次下載失敗，切換為執行緒模式: {e}")
        # fallback to ThreadPoolExecutor
        max_workers = 15
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_sid = {
                executor.submit(_screen_single_stock, sid, period, cutoff_date, strategy): sid
                for sid in stock_ids
            }
            for future in concurrent.futures.as_completed(future_to_sid):
                sid = future_to_sid[future]
                try:
                    stock_results = future.result()
                    results.extend(stock_results)
                except Exception as ex:
                    logger.error(f"執行緒模式掃描 {sid} 失敗: {ex}")
        
        results.sort(key=lambda r: r.signal_date, reverse=True)
        if stock_ids == get_all_twse_stock_ids():
            _screener_cache["timestamp"] = current_time
            _screener_cache["results"] = results
            _screener_cache["lookback_days"] = lookback_days
            _screener_cache["period"] = period
            _screener_cache["strategy"] = strategy
        return results

    # 批次下載成功，開始在記憶體中處理資料
    for sid in stock_ids:
        ticker = _to_yahoo_ticker(sid)
        try:
            if hasattr(df_all.columns, "levels") and ticker in df_all.columns.levels[0]:
                df_single = df_all[ticker].copy()
            elif ticker in df_all.columns:
                df_single = df_all.copy()
            else:
                continue
                
            if df_single.empty or df_single.dropna(how="all").empty:
                continue
                
            df_single = df_single.reset_index()
            df_single = df_single.rename(columns={
                "Date": "date",
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            })
            
            required_cols = ["date", "open", "high", "low", "close", "volume"]
            if not all(col in df_single.columns for col in required_cols):
                continue
                
            df_single = df_single[required_cols].copy()
            df_single["date"] = pd.to_datetime(df_single["date"]).dt.tz_localize(None).dt.normalize()
            df_single["stock_id"] = sid.replace(".TW", "").replace(".TWO", "")
            df_single = df_single.dropna(subset=["open", "high", "low", "close"])
            df_single = df_single.sort_values("date").reset_index(drop=True)
            
            # 計算訊號
            stock_results = _process_single_stock_df(sid, df_single, cutoff_date, strategy)
            results.extend(stock_results)
        except Exception as e:
            logger.error(f"記憶體中處理 {sid} 資料失敗: {e}")

    # 按訊號日期降冪排序（最新的在前）
    results.sort(key=lambda r: r.signal_date, reverse=True)

    # 如果是全市場掃描，則寫入快取
    if stock_ids == get_all_twse_stock_ids():
        _screener_cache["timestamp"] = current_time
        _screener_cache["results"] = results
        _screener_cache["lookback_days"] = lookback_days
        _screener_cache["period"] = period
        _screener_cache["strategy"] = strategy
        logger.info("已更新選股結果至記憶體快取")

    logger.info(f"市場批次下載與篩選完成：共發現 {len(results)} 個訊號，總耗時 {time.time() - t_start:.2f} 秒")
    return results
