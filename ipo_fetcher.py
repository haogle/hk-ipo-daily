"""
港股IPO招股信息抓取模块
主数据源: AiPO数据网 (aipo.myiqdii.com)
  - /Home/GetHKIPOInfoMore: IPO基本信息（招股价、日期、行业等）
  - /Home/GetMarginList: 孖展超认购倍数
"""

import re
import math
import requests
from datetime import datetime, date
from bs4 import BeautifulSoup
from dataclasses import dataclass


@dataclass
class IPOStock:
    """港股IPO信息"""
    code: str = ""                           # 股票代码
    name: str = ""                           # 公司名称
    price_range: str = ""                    # 招股价范围
    lot_size: int = 0                        # 每手股数
    min_cost: str = ""                       # 一手入场费
    subscription_start: str = ""             # 招股开始日期
    subscription_end: str = ""               # 招股截止日期
    listing_date: str = ""                   # 上市日期
    result_date: str = ""                    # 公布结果日期
    margin_ratio: float = 0.0               # 孖展超认购倍数
    margin_type: str = ""                    # 孖展趋势 (上升/抽飛/...)
    pe_ratio: float = 0.0                    # 市盈率
    market_cap: str = ""                     # 市值(亿)
    status: str = ""                         # 状态: 招股中/已截止/已上市
    sponsor: str = ""                        # 保荐人
    industry: str = ""                       # 行业
    raise_money: str = ""                    # 募资金额
    total_fund: float = 0.0                  # 孖展总额(亿)


BASE_URL = "https://aipo.myiqdii.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def _get_token(page_path="/aipo/index"):
    """获取 RequestVerificationToken 和 cookies"""
    resp = requests.get(f"{BASE_URL}{page_path}", headers=HEADERS, timeout=8)
    match = re.search(r'name="__RequestVerificationToken".*?value="([^"]+)"', resp.text)
    token = match.group(1) if match else ""
    return token, resp.cookies


def _format_api_date(date_str):
    """将API返回的ISO日期格式化为 YYYY-MM-DD"""
    if not date_str:
        return "--"
    try:
        return date_str[:10]
    except Exception:
        return "--"


def _determine_status(start_str, end_str, list_str):
    """根据日期判断IPO状态"""
    today = date.today()
    try:
        end_date = datetime.strptime(end_str, "%Y-%m-%d").date() if end_str != "--" else None
        list_date = datetime.strptime(list_str, "%Y-%m-%d").date() if list_str != "--" else None

        if list_date and today >= list_date:
            return "已上市"
        elif end_date and today > end_date:
            return "已截止"
        elif end_date and today <= end_date:
            return "招股中"
        else:
            return "未知"
    except Exception:
        return "未知"


def _clean_sponsor(html_str):
    """从HTML格式的保荐人字段中提取文本"""
    if not html_str:
        return ""
    soup = BeautifulSoup(str(html_str), "html.parser")
    return soup.get_text(separator=", ", strip=True)


def fetch_aipo_ipo_list() -> list:
    """从AiPO获取IPO基本信息列表"""
    token, cookies = _get_token("/aipo/index")
    url = f"{BASE_URL}/Home/GetHKIPOInfoMore"
    params = {
        "sector": "",
        "pageIndex": 1,
        "pageSize": 50,
        "v": "0.123",
    }
    api_headers = {
        **HEADERS,
        "RequestVerificationToken": token,
        "Referer": f"{BASE_URL}/aipo/index",
        "X-Requested-With": "XMLHttpRequest",
    }

    try:
        resp = requests.get(url, params=params, headers=api_headers, cookies=cookies, timeout=8)
        data = resp.json()
        if data.get("result") == 1 and data.get("data"):
            return data["data"].get("dataList", [])
    except Exception as e:
        print(f"[AiPO] IPO列表抓取失败: {e}")

    return []


def fetch_aipo_margin_list() -> dict:
    """从AiPO获取孖展超认购倍数数据，返回 {symbol: margin_info} 映射"""
    token, cookies = _get_token("/margin/index")
    url = f"{BASE_URL}/Home/GetMarginList"
    params = {
        "sector": "",
        "pageIndex": 1,
        "pageSize": 50,
        "v": "0.123",
    }
    api_headers = {
        **HEADERS,
        "RequestVerificationToken": token,
        "Referer": f"{BASE_URL}/margin/index",
        "X-Requested-With": "XMLHttpRequest",
    }

    margin_map = {}
    try:
        resp = requests.get(url, params=params, headers=api_headers, cookies=cookies, timeout=8)
        data = resp.json()
        if data.get("result") == 1 and data.get("data"):
            for item in data["data"].get("dataList", []):
                symbol = item.get("symbol", "")
                margin_map[symbol] = {
                    "marginData": item.get("marginData", 0) or 0,
                    "marginType": item.get("marginType") or "",
                    "totalFund": item.get("totalFund", 0) or 0,
                }
    except Exception as e:
        print(f"[AiPO] 孖展数据抓取失败: {e}")

    return margin_map


def get_all_ipo_stocks() -> list:
    """获取完整IPO列表，合并基本信息和孖展数据"""
    print("  正在获取IPO招股信息...")
    ipo_list = fetch_aipo_ipo_list()

    print("  正在获取孖展超认购数据...")
    margin_map = fetch_aipo_margin_list()

    stocks = []
    for item in ipo_list:
        code = item.get("symbol", "")
        start_date = _format_api_date(item.get("startdate"))
        end_date = _format_api_date(item.get("enddate"))
        list_date = _format_api_date(item.get("listedDate"))
        result_date = _format_api_date(item.get("resultDate"))

        price_floor = item.get("price_Floor")
        price_ceil = item.get("price_Ceiling")
        if price_floor is not None and price_ceil is not None:
            if price_floor == price_ceil:
                price_range = f"{price_floor:.2f}"
            else:
                price_range = f"{price_floor:.2f} - {price_ceil:.2f}"
        else:
            price_range = "--"

        pe = item.get("pe") or 0
        mcap = item.get("marketcap") or 0
        if mcap and mcap > 0:
            market_cap_str = f"{mcap / 100000000:.2f}亿" if mcap >= 100000000 else f"{mcap / 10000:.0f}万"
        else:
            market_cap_str = "--"

        # 合并孖展数据
        margin_info = margin_map.get(code, {})
        margin_data = margin_info.get("marginData", 0)
        margin_type = margin_info.get("marginType", "")
        total_fund = margin_info.get("totalFund", 0)

        stock = IPOStock(
            code=code,
            name=item.get("shortName", ""),
            price_range=price_range,
            lot_size=item.get("shares", 0) or 0,
            min_cost=str(item.get("minimumCapital", "")) if item.get("minimumCapital") else "",
            subscription_start=start_date,
            subscription_end=end_date,
            listing_date=list_date,
            result_date=result_date,
            margin_ratio=round(margin_data, 2) if margin_data else 0,
            margin_type=margin_type,
            pe_ratio=round(pe, 2) if pe else 0,
            market_cap=market_cap_str,
            status=_determine_status(start_date, end_date, list_date),
            sponsor=_clean_sponsor(item.get("sponsors", "")),
            industry=item.get("industry", ""),
            raise_money=str(item.get("raiseMoney", "")) if item.get("raiseMoney") else "",
            total_fund=round(total_fund, 2) if total_fund else 0,
        )
        stocks.append(stock)

    return sorted(stocks, key=lambda s: s.subscription_end, reverse=True)


def get_subscribing_stocks() -> list:
    """只返回正在招股中的股票"""
    return [s for s in get_all_ipo_stocks() if s.status == "招股中"]


def get_recent_ipo_stocks(days=30) -> list:
    """返回最近N天内的IPO"""
    today = date.today()
    result = []
    for stock in get_all_ipo_stocks():
        try:
            end_date = datetime.strptime(stock.subscription_end, "%Y-%m-%d").date()
            if (today - end_date).days <= days:
                result.append(stock)
        except Exception:
            result.append(stock)
    return result


if __name__ == "__main__":
    print("正在获取港股IPO数据...\n")
    stocks = get_all_ipo_stocks()
    subscribing = [s for s in stocks if s.status == "招股中"]
    print(f"\n共获取 {len(stocks)} 只IPO，其中 {len(subscribing)} 只正在招股中\n")
    for s in stocks:
        margin_str = f"{s.margin_ratio:.1f}x" if s.margin_ratio > 0 else "--"
        print(f"[{s.status}] {s.code} {s.name} | 招股价: {s.price_range} | "
              f"截止: {s.subscription_end} | 孖展: {margin_str} | "
              f"上市日: {s.listing_date} | 行业: {s.industry}")
