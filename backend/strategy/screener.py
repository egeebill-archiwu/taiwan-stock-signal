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

from backend.data.fetcher import fetch_stock_data, get_all_twse_stock_ids
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
    "2888": "新光金", "5876": "上海商銀", "2889": "國票金", "2002": "中鋼",
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
    "period": None
}
CACHE_DURATION = 300  # 快取時效為 5 分鐘 (300 秒)


def _screen_single_stock(sid: str, period: str, cutoff_date: date) -> list[ScreenerResult]:
    """掃描單一股票的輔助函式（供 ThreadPool 呼叫）"""
    try:
        df = fetch_stock_data(sid, period=period)
        if df.empty or len(df) < 25:
            return []

        # 偵測訊號
        signals = detect_all_signals(df)

        # 篩選出大於等於截止日期的訊號
        recent_signals = [s for s in signals if s.date >= cutoff_date]

        results = []
        for signal in recent_signals:
            # 計算該訊號日期的漲跌幅
            change_val = 0.0
            try:
                import pandas as pd
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

            stock_name = STOCK_NAMES.get(sid, sid)
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
        logger.error(f"掃描 {sid} 時發生錯誤: {e}")
        return []


def screen_stocks(
    stock_ids: Optional[list[str]] = None,
    period: str = "6mo",
    lookback_days: int = 5,
    force_refresh: bool = False,
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

    # 判斷是否可以使用快取：
    # 1. 不是強制整理 (force_refresh = False)
    # 2. 請求的是預設的全部主要股票 (stock_ids 為 None)
    # 3. 快取內容存在且未過期 (CACHE_DURATION 內)
    # 4. 快取的 lookback_days 與 period 相同
    current_time = time.time()
    if (not force_refresh and 
        stock_ids is None and 
        _screener_cache["results"] is not None and 
        (current_time - _screener_cache["timestamp"]) < CACHE_DURATION and
        _screener_cache["lookback_days"] == lookback_days and
        _screener_cache["period"] == period):
        logger.info(f"使用選股快取資料 (快取時間: {current_time - _screener_cache['timestamp']:.1f} 秒前)")
        return _screener_cache["results"]

    if stock_ids is None:
        stock_ids = get_all_twse_stock_ids()

    results: list[ScreenerResult] = []
    cutoff_date = date.today() - timedelta(days=lookback_days)
    total = len(stock_ids)

    logger.info(f"開始並行掃描市場... 總共 {total} 檔股票，線程池設定 15 workers")

    # 使用 ThreadPoolExecutor 並行掃描
    max_workers = 15
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有股票的掃描任務
        future_to_sid = {
            executor.submit(_screen_single_stock, sid, period, cutoff_date): sid
            for sid in stock_ids
        }

        # 收集結果
        for future in concurrent.futures.as_completed(future_to_sid):
            sid = future_to_sid[future]
            try:
                stock_results = future.result()
                results.extend(stock_results)
            except Exception as e:
                logger.error(f"並行掃描 {sid} 時發生異常: {e}")

    # 按訊號日期降冪排序（最新的在前）
    results.sort(key=lambda r: r.signal_date, reverse=True)

    # 如果是全市場掃描，則寫入快取
    if stock_ids == get_all_twse_stock_ids():
        _screener_cache["timestamp"] = current_time
        _screener_cache["results"] = results
        _screener_cache["lookback_days"] = lookback_days
        _screener_cache["period"] = period
        logger.info("已更新選股結果至記憶體快取")

    logger.info(f"市場並行掃描完成：共發現 {len(results)} 個訊號")
    return results
