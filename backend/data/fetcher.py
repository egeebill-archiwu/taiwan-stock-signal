"""
台股布林通道交易訊號系統 - 資料擷取模組

使用 yfinance 從 Yahoo Finance 取得台股 OHLCV 資料。
台股代號格式：XXXX.TW（上市）或 XXXX.TWO（上櫃）。
"""

import logging
from typing import Optional

import pandas as pd
import yfinance as yf

from backend.config import DEFAULT_FETCH_PERIOD, TWSE_SUFFIX, TPEX_SUFFIX

logger = logging.getLogger(__name__)


def _to_yahoo_ticker(stock_id: str) -> str:
    """
    將股票代號轉換為 Yahoo Finance 格式

    若已包含 .TW 或 .TWO 後綴則直接回傳，否則預設加上 .TW（上櫃則加上 .TWO）。
    """
    stock_id = stock_id.strip()
    if stock_id.upper().endswith(".TW") or stock_id.upper().endswith(".TWO"):
        return stock_id
    
    # 台灣主要市值前 100 大中的上櫃股票 (TPEX)
    otc_stocks = {"3529", "4743", "5347", "6488", "6547", "8069"}
    if stock_id in otc_stocks:
        return f"{stock_id}{TPEX_SUFFIX}"
        
    return f"{stock_id}{TWSE_SUFFIX}"


def fetch_stock_data(
    stock_id: str,
    period: str = DEFAULT_FETCH_PERIOD,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> pd.DataFrame:
    """
    擷取單一股票的歷史 OHLCV 資料

    Parameters
    ----------
    stock_id : str
        台股代號，例如 '2330' 或 '2330.TW'
    period : str
        資料期間，例如 '1y'、'6mo'、'3mo'（當 start/end 未指定時使用）
    start : str, optional
        起始日期，格式 'YYYY-MM-DD'
    end : str, optional
        結束日期，格式 'YYYY-MM-DD'

    Returns
    -------
    pd.DataFrame
        包含 date, stock_id, open, high, low, close, volume 欄位的 DataFrame
    """
    ticker_str = _to_yahoo_ticker(stock_id)
    logger.info(f"正在擷取 {ticker_str} 的歷史資料...")

    try:
        ticker = yf.Ticker(ticker_str)

        if start and end:
            df = ticker.history(start=start, end=end, auto_adjust=True)
        else:
            df = ticker.history(period=period, auto_adjust=True)

        if df.empty:
            logger.warning(f"{ticker_str} 無可用資料")
            return pd.DataFrame()

        # 整理欄位名稱
        df = df.reset_index()
        df = df.rename(columns={
            "Date": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        })

        # 只保留需要的欄位
        df = df[["date", "open", "high", "low", "close", "volume"]].copy()

        # 移除時區資訊，統一為日期格式
        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.normalize()

        # 加入股票代號欄位（使用原始代號，不含 .TW 後綴）
        raw_id = stock_id.replace(".TW", "").replace(".TWO", "")
        df["stock_id"] = raw_id

        # 移除含有 NaN 的列
        df = df.dropna(subset=["open", "high", "low", "close"])

        # 依日期排序
        df = df.sort_values("date").reset_index(drop=True)

        logger.info(f"成功擷取 {ticker_str} 共 {len(df)} 筆資料")
        return df

    except Exception as e:
        logger.error(f"擷取 {ticker_str} 資料時發生錯誤: {e}")
        return pd.DataFrame()


def fetch_multiple_stocks(
    stock_ids: list[str],
    period: str = DEFAULT_FETCH_PERIOD,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> dict[str, pd.DataFrame]:
    """
    批次擷取多檔股票的歷史資料

    Parameters
    ----------
    stock_ids : list[str]
        股票代號清單
    period : str
        資料期間
    start : str, optional
        起始日期
    end : str, optional
        結束日期

    Returns
    -------
    dict[str, pd.DataFrame]
        以股票代號為鍵值、DataFrame 為內容的字典
    """
    results: dict[str, pd.DataFrame] = {}

    for sid in stock_ids:
        df = fetch_stock_data(sid, period=period, start=start, end=end)
        if not df.empty:
            raw_id = sid.replace(".TW", "").replace(".TWO", "")
            results[raw_id] = df

    logger.info(f"批次擷取完成，成功取得 {len(results)}/{len(stock_ids)} 檔股票資料")
    return results


def get_all_twse_stock_ids() -> list[str]:
    """
    取得台股上市主要股票代號清單（市值前 100 大）

    此為靜態清單，涵蓋台灣 50、中型 100 等主要成分股。
    實際使用時可改為動態抓取。

    Returns
    -------
    list[str]
        股票代號清單（不含 .TW 後綴）
    """
    # 台灣市值前 100 大上市公司（2024 年版本，定期更新）
    major_stocks = [
        # ===== 半導體 =====
        "2330",  # 台積電
        "2303",  # 聯電
        "2454",  # 聯發科
        "3711",  # 日月光投控
        "2379",  # 瑞昱
        "3034",  # 聯詠
        "6415",  # 矽力-KY
        "3529",  # 力旺
        "2408",  # 南亞科
        "3443",  # 創意
        # ===== 電子零組件 =====
        "2317",  # 鴻海
        "2382",  # 廣達
        "2356",  # 英業達
        "2353",  # 宏碁
        "3231",  # 緯創
        "2301",  # 光寶科
        "2357",  # 華碩
        "4938",  # 和碩
        "3017",  # 奇鋐
        "2345",  # 智邦
        # ===== 金融 =====
        "2881",  # 富邦金
        "2882",  # 國泰金
        "2891",  # 中信金
        "2886",  # 兆豐金
        "2884",  # 玉山金
        "2885",  # 元大金
        "2887",  # 台新金
        "2890",  # 永豐金
        "2880",  # 華南金
        "2883",  # 開發金
        "2892",  # 第一金
        "5880",  # 合庫金
        "2888",  # 新光金 (保留) / 2324 仁寶
        "2324",  # 仁寶
        "5876",  # 上海商銀
        "2889",  # 國票金
        # ===== 傳統產業 =====
        "2002",  # 中鋼
        "1301",  # 台塑
        "1303",  # 南亞
        "1326",  # 台化
        "6505",  # 台塑化
        "1101",  # 台泥
        "1102",  # 亞泥
        "1216",  # 統一
        "2912",  # 統一超
        "1476",  # 儒鴻
        "9910",  # 豐泰
        "2207",  # 和泰車
        "9921",  # 巨大
        "1590",  # 亞德客-KY
        "2201",  # 裕隆
        # ===== 電信 / 通訊 =====
        "2412",  # 中華電
        "3045",  # 台灣大
        "4904",  # 遠傳
        # ===== 航運 =====
        "2603",  # 長榮
        "2609",  # 陽明
        "2615",  # 萬海
        "2610",  # 華航
        "2618",  # 長榮航
        # ===== 鋼鐵 / 水泥 / 塑化 =====
        "2006",  # 東和鋼鐵
        "2014",  # 中鴻
        "1312",  # 國喬
        "1304",  # 台聚
        # ===== 電子 - 光電 / 面板 =====
        "2409",  # 友達
        "3481",  # 群創
        "2474",  # 可成
        "3008",  # 大立光
        "6269",  # 台郡
        # ===== 電子 - PCB / 被動元件 =====
        "2327",  # 國巨
        "3037",  # 欣興
        "4958",  # 臻鼎-KY
        "8046",  # 南電
        "2492",  # 華新科
        # ===== 電子 - IC 設計 / 通路 =====
        "2377",  # 微星
        "3702",  # 大聯大
        "6488",  # 環球晶
        "5347",  # 世界
        "2404",  # 漢唐
        # ===== 食品 / 生技 =====
        "1227",  # 佳格
        "4743",  # 合一
        "6446",  # 藥華藥
        "1795",  # 美時
        # ===== 營建 / 資產 =====
        "2504",  # 國產
        "2542",  # 興富發
        "5534",  # 長虹
        "2545",  # 皇翔
        # ===== 紡織 / 橡膠 =====
        "1402",  # 遠東新
        "2105",  # 正新
        # ===== 其他重要個股 =====
        "2308",  # 台達電
        "3661",  # 世芯-KY
        "2395",  # 研華
        "6409",  # 旭隼
        "2049",  # 上銀
        "8069",  # 元太
        "1504",  # 東元
        "2376",  # 技嘉
        "6239",  # 力成
        "5871",  # 中租-KY
        "6756",  # 威鋒電子
        "3653",  # 健策
        "6547",  # 高端疫苗
        "2383",  # 台光電
    ]

    return major_stocks


import functools

@functools.lru_cache(maxsize=1000)
def get_stock_name(stock_id: str) -> str:
    """
    取得股票名稱（繁體中文）

    優先從本地對照表查詢，若無則透過 TWSE API 查詢。
    """
    import requests

    clean_id = stock_id.replace(".TW", "").replace(".TWO", "").strip()

    # 台灣主要股票代碼對照表
    local_names = {
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
        "2383": "台光電",
    }

    if clean_id in local_names:
        return local_names[clean_id]

    try:
        url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_{clean_id}.tw|otc_{clean_id}.tw"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            res = r.json()
            if "msgArray" in res and len(res["msgArray"]) > 0:
                info = res["msgArray"][0]
                if "n" in info and info["n"]:
                    return info["n"].strip()
    except Exception as e:
        logger.warning(f"無法從 TWSE API 取得股票 {clean_id} 名稱: {e}")

    return clean_id
