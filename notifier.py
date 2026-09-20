"""
Webhook 通知模块
═══════════════════════════════════════════════════════════════
支持的渠道 (任选, 配置在 .env):
  - Slack   : SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
  - 钉钉    : DINGTALK_WEBHOOK_URL=https://oapi.dingtalk.com/robot/send?access_token=...
  - 企业微信 : WECOM_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=...
  - Telegram: TELEGRAM_NOTIFY_CHAT_ID=123456789 (用 TELEGRAM_BOT_TOKEN 发)

用法:
  from notifier import notify
  notify("🚨 Bot 出错了", "rate limit hit")
"""

import asyncio
import os
from datetime import datetime

import aiohttp
from dotenv import load_dotenv

load_dotenv()


SLACK_WEBHOOK   = os.getenv("SLACK_WEBHOOK_URL", "")
DINGTALK_WEBHOOK = os.getenv("DINGTALK_WEBHOOK_URL", "")
WECOM_WEBHOOK   = os.getenv("WECOM_WEBHOOK_URL", "")
TELEGRAM_TOKEN  = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT   = os.getenv("TELEGRAM_NOTIFY_CHAT_ID", "")


async def _post(url: str, payload: dict):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json=payload, timeout=10) as r:
                return r.status < 300
    except Exception as e:
        print(f"   ⚠️ webhook 发送失败: {e}")
        return False


async def notify(title: str, body: str = "", level: str = "info"):
    """发通知到所有配置了的渠道
    level: info / warning / error
    """
    emoji = {"info": "ℹ️", "warning": "⚠️", "error": "🚨"}.get(level, "ℹ️")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    text = f"{emoji} {title}\n{body}\n\n_🕐 {ts}_"

    tasks = []

    # Slack
    if SLACK_WEBHOOK:
        tasks.append(_post(SLACK_WEBHOOK, {"text": text}))

    # 钉钉 (markdown)
    if DINGTALK_WEBHOOK:
        tasks.append(_post(DINGTALK_WEBHOOK, {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": f"## {emoji} {title}\n\n{body}\n\n> {ts}",
            },
        }))

    # 企业微信 (markdown)
    if WECOM_WEBHOOK:
        tasks.append(_post(WECOM_WEBHOOK, {
            "msgtype": "markdown",
            "markdown": {"content": f"## {emoji} {title}\n\n{body}\n\n> {ts}"},
        }))

    # Telegram
    if TELEGRAM_TOKEN and TELEGRAM_CHAT:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        tasks.append(_post(url, {"chat_id": TELEGRAM_CHAT, "text": text}))

    if not tasks:
        return  # 没配置任何渠道, 静默

    results = await asyncio.gather(*tasks)
    sent = sum(1 for r in results if r)
    if sent > 0:
        print(f"   📢 通知已发送 ({sent} 个渠道)")


# ── 快捷模板 ──

async def notify_error(title: str, body: str = ""):
    await notify(title, body, level="error")


async def notify_warning(title: str, body: str = ""):
    await notify(title, body, level="warning")


async def notify_daily_summary(stats: dict):
    """每日摘要 (晚上 21:00 调)"""
    body = (
        f"📊 **今日互动**\n"
        f"  评论: {stats.get('comments', 0)}\n"
        f"  点赞: {stats.get('likes', 0)}\n"
        f"  关注: {stats.get('follows', 0)}\n"
        f"  扫到: {stats.get('scanned', 0)}\n"
        f"  触达: {stats.get('reach', 0)}\n"
        f"  平均分: {stats.get('avg_score', 0):.2f}"
    )
    await notify("Daily Summary", body, level="info")