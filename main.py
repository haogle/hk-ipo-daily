#!/usr/bin/env python3
"""
港股打新助手 - HK IPO Subscription Tool
========================================
用法:
  python3 main.py              # 完整报告
  python3 main.py --subscribing # 只看正在招股中的
  python3 main.py --detail      # 详细模式（显示保荐人等）
"""

import argparse
from datetime import datetime, date

from ipo_fetcher import get_all_ipo_stocks


# ANSI颜色
class C:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"
    WHITE = "\033[97m"
    BG_GRAY = "\033[100m"


def _deadline_str(end_str):
    """截止日期显示：今天截止 / MM-DD (剩X天)"""
    try:
        end = datetime.strptime(end_str, "%Y-%m-%d").date()
        delta = (end - date.today()).days
        short = end.strftime("%m-%d")
        if delta == 0:
            return "今天截止"
        elif delta > 0:
            return short
        else:
            return short
    except Exception:
        return end_str


def _margin_color(ratio):
    if ratio >= 100:
        return C.RED + C.BOLD
    elif ratio >= 30:
        return C.MAGENTA + C.BOLD
    elif ratio >= 10:
        return C.YELLOW + C.BOLD
    elif ratio > 0:
        return C.GREEN
    return C.DIM


def _display_width(s):
    """计算字符串显示宽度（中文算2，其他算1）"""
    w = 0
    for ch in s:
        if '\u4e00' <= ch <= '\u9fff' or '\u3000' <= ch <= '\u303f' or '\uff00' <= ch <= '\uffef':
            w += 2
        else:
            w += 1
    return w


def _pad(text, width, align="center"):
    """按显示宽度填充字符串"""
    dw = _display_width(text)
    pad_total = width - dw
    if pad_total <= 0:
        return text
    if align == "center":
        left = pad_total // 2
        right = pad_total - left
        return " " * left + text + " " * right
    elif align == "left":
        return text + " " * pad_total
    else:
        return " " * pad_total + text


def print_table(stocks, title):
    """打印表格"""
    if not stocks:
        return

    # 按孖展倍数从高到低排序
    stocks = sorted(stocks, key=lambda s: s.margin_ratio, reverse=True)

    COL = [10, 14, 14, 12, 10]  # 代码, 名称, 孖展超购, 截止日期, 上市日
    total_w = sum(COL) + 4  # 加上间距

    # 表头
    print(f"\n  {C.BOLD}{title} ({len(stocks)} 只){C.RESET}\n")
    hdr = (f"  {C.BG_GRAY}{C.WHITE}{C.BOLD}"
           f"{_pad('代码', COL[0])}"
           f"{_pad('名称', COL[1])}"
           f"{_pad('孖展超购', COL[2])}"
           f"{_pad('截止日期', COL[3])}"
           f"{_pad('上市日', COL[4])}"
           f"{C.RESET}")
    print(hdr)
    print(f"  {C.DIM}{'─' * total_w}{C.RESET}")

    # 数据行
    for s in stocks:
        margin_str = f"{s.margin_ratio:.1f}倍" if s.margin_ratio > 0 else "--"
        m_color = _margin_color(s.margin_ratio)
        deadline = _deadline_str(s.subscription_end)
        try:
            list_short = datetime.strptime(s.listing_date, "%Y-%m-%d").strftime("%m-%d")
        except Exception:
            list_short = s.listing_date

        line = (f"  {_pad(s.code, COL[0])}"
                f"{_pad(s.name, COL[1])}"
                f"{m_color}{_pad(margin_str, COL[2])}{C.RESET}"
                f"{_pad(deadline, COL[3])}"
                f"{_pad(list_short, COL[4])}")
        print(line)

    print(f"  {C.DIM}{'─' * total_w}{C.RESET}")


def print_detail_table(stocks, title):
    """详细模式表格"""
    if not stocks:
        return

    stocks = sorted(stocks, key=lambda s: s.margin_ratio, reverse=True)

    print(f"\n  {C.BOLD}{title} ({len(stocks)} 只){C.RESET}\n")

    for i, s in enumerate(stocks, 1):
        margin_str = f"{s.margin_ratio:.1f}倍" if s.margin_ratio > 0 else "--"
        m_color = _margin_color(s.margin_ratio)
        deadline = _deadline_str(s.subscription_end)

        print(f"  {C.BOLD}{i}. [{s.code}] {s.name}{C.RESET}  {C.DIM}{s.industry}{C.RESET}")
        print(f"     招股价: {C.CYAN}{s.price_range} HKD{C.RESET}  每手: {s.lot_size}股  "
              f"市盈率: {s.pe_ratio:.1f}  市值: {s.market_cap}")
        print(f"     招股: {s.subscription_start} ~ {s.subscription_end}  "
              f"上市: {s.listing_date}  结果: {s.result_date}")
        print(f"     孖展超购: {m_color}{margin_str}{C.RESET}")
        if s.sponsor:
            print(f"     保荐人: {C.DIM}{s.sponsor}{C.RESET}")
        print()


def main():
    parser = argparse.ArgumentParser(description="港股打新助手")
    parser.add_argument("--subscribing", action="store_true", help="只显示正在招股中的新股")
    parser.add_argument("--detail", action="store_true", help="详细模式")
    args = parser.parse_args()

    print(f"\n  {C.CYAN}{C.BOLD}港股打新助手{C.RESET}  "
          f"{C.DIM}{datetime.now().strftime('%Y-%m-%d %H:%M')}{C.RESET}")
    print(f"  {C.DIM}数据来源: aipo.myiqdii.com{C.RESET}")

    all_stocks = get_all_ipo_stocks()

    subscribing = [s for s in all_stocks if s.status == "招股中"]
    closed = [s for s in all_stocks if s.status == "已截止"]
    listed = [s for s in all_stocks if s.status == "已上市"]

    printer = print_detail_table if args.detail else print_table

    printer(subscribing, "正在招股中")

    if not args.subscribing:
        printer(closed, "已截止待上市")
        printer(listed, "近期已上市")

    print(f"\n  {C.DIM}* 孖展超购倍数仅供参考，打新有风险。{C.RESET}\n")


if __name__ == "__main__":
    main()
