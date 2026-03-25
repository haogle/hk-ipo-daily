"""
Vercel Serverless Function - 港股打新日报
每天定时抓取IPO数据并推送到飞书
"""

import os
import json
import requests
from http.server import BaseHTTPRequestHandler
from datetime import datetime, date

from ipo_fetcher import get_all_ipo_stocks


FEISHU_WEBHOOK_URL = os.environ.get(
    "FEISHU_WEBHOOK_URL",
    "https://open.feishu.cn/open-apis/bot/v2/hook/fb6f9fac-8f2f-4232-a786-1e5890b46691"
)


def _deadline_str(end_str):
    try:
        end = datetime.strptime(end_str, "%Y-%m-%d").date()
        delta = (end - date.today()).days
        if delta == 0:
            return "今天截止"
        elif delta > 0:
            return f"{end.strftime('%m-%d')} (剩{delta}天)"
        return end.strftime("%m-%d")
    except Exception:
        return end_str


def build_feishu_card(subscribing, closed):
    """构建飞书Interactive Card消息"""
    elements = []

    # 正在招股
    if subscribing:
        # 表头
        header_cols = {
            "tag": "column_set",
            "flex_mode": "none",
            "background_style": "grey",
            "columns": [
                {"tag": "column", "width": "weighted", "weight": 2,
                 "elements": [{"tag": "markdown", "content": "**代码**"}]},
                {"tag": "column", "width": "weighted", "weight": 3,
                 "elements": [{"tag": "markdown", "content": "**名称**"}]},
                {"tag": "column", "width": "weighted", "weight": 3,
                 "elements": [{"tag": "markdown", "content": "**孖展超购**"}]},
                {"tag": "column", "width": "weighted", "weight": 3,
                 "elements": [{"tag": "markdown", "content": "**截止日期**"}]},
                {"tag": "column", "width": "weighted", "weight": 2,
                 "elements": [{"tag": "markdown", "content": "**上市日**"}]},
            ]
        }
        elements.append(header_cols)

        # 数据行
        for s in sorted(subscribing, key=lambda x: x.margin_ratio, reverse=True):
            margin_str = f"**{s.margin_ratio:.1f}倍**" if s.margin_ratio >= 100 else (
                f"{s.margin_ratio:.1f}倍" if s.margin_ratio > 0 else "--"
            )
            deadline = _deadline_str(s.subscription_end)
            try:
                list_short = datetime.strptime(s.listing_date, "%Y-%m-%d").strftime("%m-%d")
            except Exception:
                list_short = s.listing_date

            row = {
                "tag": "column_set",
                "flex_mode": "none",
                "columns": [
                    {"tag": "column", "width": "weighted", "weight": 2,
                     "elements": [{"tag": "markdown", "content": s.code}]},
                    {"tag": "column", "width": "weighted", "weight": 3,
                     "elements": [{"tag": "markdown", "content": s.name}]},
                    {"tag": "column", "width": "weighted", "weight": 3,
                     "elements": [{"tag": "markdown", "content": margin_str}]},
                    {"tag": "column", "width": "weighted", "weight": 3,
                     "elements": [{"tag": "markdown", "content": deadline}]},
                    {"tag": "column", "width": "weighted", "weight": 2,
                     "elements": [{"tag": "markdown", "content": list_short}]},
                ]
            }
            elements.append(row)
    else:
        elements.append({
            "tag": "markdown",
            "content": "暂无正在招股的新股"
        })

    elements.append({"tag": "hr"})

    # 已截止待上市
    if closed:
        elements.append({
            "tag": "markdown",
            "content": f"**已截止待上市 ({len(closed)} 只)**"
        })
        lines = []
        for s in sorted(closed, key=lambda x: x.listing_date):
            margin_str = f"{s.margin_ratio:.1f}倍" if s.margin_ratio > 0 else "--"
            try:
                list_short = datetime.strptime(s.listing_date, "%Y-%m-%d").strftime("%m-%d")
            except Exception:
                list_short = s.listing_date
            lines.append(f"{s.code} {s.name} | 孖展: {margin_str} | 上市: {list_short}")
        elements.append({
            "tag": "markdown",
            "content": "\n".join(lines)
        })
        elements.append({"tag": "hr"})

    # 底部
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    elements.append({
        "tag": "note",
        "elements": [{
            "tag": "plain_text",
            "content": f"数据来源: aipo.myiqdii.com | {now_str}"
        }]
    })

    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"港股打新日报 ({date.today().strftime('%m/%d')})"
                },
                "template": "orange"
            },
            "elements": elements
        }
    }


def send_to_feishu(card):
    """发送卡片消息到飞书"""
    resp = requests.post(
        FEISHU_WEBHOOK_URL,
        json=card,
        headers={"Content-Type": "application/json"},
        timeout=10
    )
    return resp.status_code, resp.text


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            stocks = get_all_ipo_stocks()
            subscribing = [s for s in stocks if s.status == "招股中"]
            closed = [s for s in stocks if s.status == "已截止"]

            card = build_feishu_card(subscribing, closed)
            status_code, resp_text = send_to_feishu(card)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            result = {
                "ok": True,
                "subscribing": len(subscribing),
                "closed": len(closed),
                "feishu_status": status_code,
                "feishu_response": resp_text,
            }
            self.wfile.write(json.dumps(result, ensure_ascii=False).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode())
