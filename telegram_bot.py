"""
Telegram 拟人 Bot
═══════════════════════════════════════════════════════════════
复用:
  - memory.py    → SQLite 长期记忆
  - analyzer.py  → 智能打分 + 日志
  - 同 SYSTEM_PROMPT / 错别字 / 速率限制

独立:
  - 不用 python-telegram-bot, 直接 HTTP 调 Telegram Bot API
  - 用 long polling 拉消息
  - 减少依赖, 单文件能跑

用法:
  1. 找 @BotFather 拿 token
  2. .env 里加 TELEGRAM_BOT_TOKEN=...
  3. pip install aiohttp openai python-dotenv
  4. python telegram_bot.py
"""

import asyncio
import os
import random
import sys
import time
from datetime import datetime

from dotenv import load_dotenv
from openai import AsyncOpenAI

import memory
import analyzer

load_dotenv()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  配置
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
LLM_API_KEY    = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL   = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
LLM_MODEL      = os.getenv("LLM_MODEL", "deepseek-chat")

WATCH_CHATS = [c for c in os.getenv("TELEGRAM_WATCH_CHATS", "").split(",") if c]

SYSTEM_PROMPT = os.getenv("TELEGRAM_SYSTEM_PROMPT", """你是一个友好、幽默、爱分享的 bot。
回复简短 (不超过 80 字), 偶尔带 emoji, 不用太正式。""")

MAX_REPLIES_PER_HOUR = int(os.getenv("MAX_TG_REPLIES_PER_HOUR", "10"))
DRY_RUN = os.getenv("DRY_RUN", "1") == "1"
TYPO_PROB = float(os.getenv("TYPO_PROB", "0.08"))


def make_llm():
    return AsyncOpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)


async def generate_reply(llm, text, user_name, user_ctx):
    history = user_ctx.get("history", [])
    history_str = "\n".join(f"- {h}" for h in history[-5:]) if history else "(首次)"

    prompt = f"""{SYSTEM_PROMPT}

[用户]: @{user_name}
[历史]: {history_str}
[消息]: {text}

[你的回复, 不超过 80 字]:"""

    try:
        resp = await llm.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=200,
        )
        reply = resp.choices[0].message.content.strip()
        try:
            reply = memory.inject_typo(reply, prob=TYPO_PROB)
        except AttributeError:
            pass
        return reply
    except Exception as e:
        print(f"   ⚠️ LLM 出错: {e}")
        return None


async def humanize_delay(min_s=2, max_s=10):
    delay = random.gauss((min_s + max_s) / 2, (max_s - min_s) / 4)
    delay = max(min_s, min(max_s, delay))
    print(f"   💤 等待 {delay:.1f}s...")
    await asyncio.sleep(delay)


async def main():
    if not TELEGRAM_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN 没设置 (找 @BotFather 拿)")
        sys.exit(1)
    if not LLM_API_KEY:
        print("❌ LLM_API_KEY 没设置")
        sys.exit(1)

    memory.init_db()
    analyzer.extend_db()
    llm = make_llm()

    count = 0
    hour_reset = time.time()

    print("🚀 Telegram 拟人 Bot 启动")
    print(f"   模式: {'🟡 DRY_RUN' if DRY_RUN else '🔴 LIVE'}")
    print(f"   LLM: {LLM_MODEL}")
    print(f"   监控: {WATCH_CHATS if WATCH_CHATS else '[所有消息]'}")
    print(f"   速率: {MAX_REPLIES_PER_HOUR} 条/小时\n")

    import aiohttp
    base = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
    offset = 0
    cycle = 0

    async with aiohttp.ClientSession() as session:
        print("🔑 Long polling 启动...")
        print("✅ Telegram Bot 就绪, 等待消息...\n")

        while True:
            cycle += 1
            if time.time() - hour_reset > 3600:
                count = 0
                hour_reset = time.time()
                print(f"\n⏰ 每小时计数重置")

            if count >= MAX_REPLIES_PER_HOUR:
                wait = (3600 - (time.time() - hour_reset)) / 60
                print(f"\n⏸️  本小时已达上限, 等 {wait:.0f} 分钟")
                await asyncio.sleep(600)
                continue

            try:
                async with session.get(
                    f"{base}/getUpdates",
                    params={"offset": offset, "timeout": 30, "allowed_updates": '["message"]'},
                    timeout=45,
                ) as resp:
                    data = await resp.json()
                    if not data.get("ok"):
                        print(f"   ❌ API: {data}")
                        await asyncio.sleep(10)
                        continue

                    updates = data.get("result", [])

                    for upd in updates:
                        offset = max(offset, upd["update_id"] + 1)
                        msg = upd.get("message")
                        if not msg:
                            continue

                        chat_id = msg["chat"]["id"]
                        user_id = str(msg["from"]["id"])
                        user_name = msg["from"].get("username") or msg["from"].get("first_name", "x")
                        text = msg.get("text", "")

                        if not text or text.startswith("/"):
                            continue
                        if WATCH_CHATS and str(chat_id) not in WATCH_CHATS and user_name not in WATCH_CHATS:
                            continue

                        scores = analyzer.score_tweet(text, user_name)
                        score = scores["total"]
                        print(f"\n📨 来自 @{user_name}: {text[:80]}")
                        print(f"   评分: {score:.2f}")

                        action = analyzer.decide_action(
                            score,
                            {"comment": count, "like": 999, "follow": 0},
                            {"comment": MAX_REPLIES_PER_HOUR, "like": 999, "follow": 0},
                        )
                        if action != "comment":
                            print(f"   ⏭️  跳过 (score={score:.2f})")
                            continue

                        memory.upsert_user(user_id, user_name)
                        user_ctx = memory.get_user_context(user_id)
                        print(f"   🤖 LLM 生成中...")
                        reply = await generate_reply(llm, text, user_name, user_ctx)
                        if not reply:
                            continue
                        print(f"   💬 回复: {reply}")

                        await humanize_delay(2, 8)

                        if DRY_RUN:
                            print(f"   [DRY RUN] ✋ 不实际发送")
                        else:
                            async with session.post(
                                f"{base}/sendMessage",
                                json={"chat_id": chat_id, "text": reply},
                            ) as r:
                                result = await r.json()
                                if result.get("ok"):
                                    print(f"   ✅ 已发送")
                                else:
                                    print(f"   ❌ 发送失败: {result}")

                        memory.save_reply(user_id, text, reply)
                        analyzer.log_action(user_id, str(chat_id), "comment", "telegram")
                        count += 1

                        if count >= MAX_REPLIES_PER_HOUR:
                            break

                    if not updates:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] 💤 第 {cycle} 轮无新消息")

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"\n❌ 错误: {e}")
                await asyncio.sleep(10)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Telegram Bot 已退出 (Ctrl+C)")