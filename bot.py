"""
Twitter/X 拟人自动互动 Bot v2 - 全功能版
═══════════════════════════════════════════════════════════════
工作流程:
  1. 监控指定 hashtag 列表
  2. 看到新推文 → 行为多样性 (70% 评论 / 20% 点赞 / 10% 关注)
  3. 拟人化随机延迟 (高斯分布)
  4. 定时自动发帖 (每天 3 次, LLM 生成内容)
  5. 自动回关 (新粉丝 → 自动 follow back)
  6. SQLite 长期记忆 + 用户画像 + 错别字注入
  7. 默认 DRY_RUN, 只打印不发

首次使用:
  1. cp .env.example .env   →  填入 Twitter 账号 + LLM API key
  2. python bot.py          →  自动登录 + 监控 + 自动发帖

依赖:
  pip install twikit openai python-dotenv
"""

import asyncio
import os
import random
import time
from datetime import datetime, timedelta

from dotenv import load_dotenv
from openai import AsyncOpenAI
from twikit import Client

import memory  # 记忆模块 (SQLite + 用户画像 + 错别字)

load_dotenv()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  配置区 (改这里就能改行为)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DRY_RUN = True            # True=只打印不实际发, False=真发
WATCH_HASHTAGS = ["indiehackers", "AItools", "buildinpublic"]
SCAN_INTERVAL_SEC = 180   # 扫描间隔 (秒)
COOKIES_FILE = "twitter_cookies.json"

# ── 速率限制 (每小时) ──
MAX_REPLIES_PER_HOUR = 3  # 评论
MAX_LIKES_PER_HOUR   = 8  # 点赞
MAX_FOLLOWS_PER_HOUR = 2  # 关注

# ── 行为多样性 (看到一条推文, 概率分布) ──
PROB_COMMENT = 0.65       # 65% 评论
PROB_LIKE    = 0.25       # 25% 只点赞 (不评论)
PROB_FOLLOW  = 0.10       # 10% 关注作者

# ── 自动发帖 ──
ENABLE_AUTO_POST = True
POST_TIMES = ["09:30", "14:00", "21:30"]   # 每天 3 次 (24h 制)
POST_TOPICS = ["AI 工具", "产品思考", "创业感悟", "代码片段", "读书笔记"]

# ── 自动回关 ──
ENABLE_AUTO_FOLLOW_BACK = True

# LLM 配置 (默认 DeepSeek, 改成 openai/anthropic 也行)
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "deepseek")
LLM_API_KEY  = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
LLM_MODEL    = os.getenv("LLM_MODEL", "deepseek-chat")

# Twitter 登录信息 (首次登录需要, 之后用 cookie)
TWITTER_USERNAME = os.getenv("TWITTER_USERNAME", "")
TWITTER_EMAIL    = os.getenv("TWITTER_EMAIL", "")
TWITTER_PASSWORD = os.getenv("TWITTER_PASSWORD", "")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  拟人化提示词
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SYSTEM_PROMPT = """你是一个真实的人类用户，活跃在 Twitter/X 上。
你的风格特点:
- 偶尔带点幽默，会用网络流行语
- 回复短小精悍（不超过 140 字）
- 偶尔用一两个语气词（哈哈、确实、卧槽、离谱、nice）
- 偶尔打错字（但不要太多，每 3-4 条才一个）
- 看到技术/创业/AI 内容会很感兴趣
- 不要带 # 标签
- 不要用太多感叹号
- 像在跟朋友聊天，不像在写邮件
- 用中文回复，除非推文是英文"""

USER_PROMPT = """推文内容: {tweet_text}

作者: @{username}

请直接输出你的回复，不要加任何前缀、引号或解释。"""

POST_PROMPT = """你现在要发一条原创推文。

主题方向: {topic}

风格要求:
- 像真人随口发的，不是营销文案
- 1-2 句话，不超过 140 字
- 可以是观点、吐槽、问句、感悟
- 不要带 # 标签
- 不要用太多感叹号
- 用中文

请只输出推文内容，不要其他解释。"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  工具函数
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def generate_reply(llm: AsyncOpenAI, tweet_text: str, username: str, user_ctx: dict = None) -> str:
    """LLM 生成个性化回复 (注入用户上下文)"""
    base_prompt = SYSTEM_PROMPT
    if user_ctx and user_ctx.get("known"):
        base_prompt = memory.build_system_prompt(SYSTEM_PROMPT, user_ctx)

    response = await llm.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": base_prompt},
            {"role": "user",   "content": USER_PROMPT.format(
                tweet_text=tweet_text, username=username
            )},
        ],
        temperature=0.85,
        max_tokens=200,
    )
    reply = response.choices[0].message.content.strip()
    reply = memory.maybe_inject_typo(reply, prob=0.08)
    return reply


async def generate_post(llm: AsyncOpenAI, topic: str) -> str:
    """LLM 生成一条原创推文 (用于定时自动发帖)"""
    response = await llm.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": POST_PROMPT.format(topic=topic)},
        ],
        temperature=0.9,
        max_tokens=160,
    )
    post = response.choices[0].message.content.strip()
    # 清理掉 LLM 有时会加的引号
    post = post.strip('"').strip("'").strip("「").strip("」")
    post = memory.maybe_inject_typo(post, prob=0.05)
    return post


def choose_action() -> str:
    """行为多样性: 看到一条推文, 随机选 'comment' / 'like' / 'follow'"""
    r = random.random()
    if r < PROB_COMMENT:
        return "comment"
    elif r < PROB_COMMENT + PROB_LIKE:
        return "like"
    else:
        return "follow"


async def humanize_delay(min_s: int = 30, max_s: int = 120):
    """拟人化随机延迟 (高斯分布)"""
    mu    = (min_s + max_s) / 2
    sigma = (max_s - min_s) / 4
    delay = max(min_s, min(max_s, random.gauss(mu, sigma)))
    print(f"   💤 拟人化等待 {delay:.0f} 秒...")
    await asyncio.sleep(delay)


async def short_delay(min_s: int = 5, max_s: int = 20):
    """短延迟 (点赞/关注用, 1-2 个动作之间)"""
    delay = random.uniform(min_s, max_s)
    print(f"   ⏱️  短等待 {delay:.0f} 秒...")
    await asyncio.sleep(delay)


async def reply_to_tweet(tweet, text: str, dry_run: bool):
    """回复一条推文"""
    if dry_run:
        print(f"   [DRY RUN] ✋ 不实际发送回复")
        return
    await tweet.reply(text)
    print(f"   ✅ 已回复")


async def like_tweet(client: Client, tweet_id: str, dry_run: bool):
    """点赞"""
    if dry_run:
        print(f"   [DRY RUN] ❤️  不实际点赞")
        return
    await client.favorite_tweet(tweet_id)
    print(f"   ❤️  已点赞")


async def follow_user(client: Client, user_id: str, dry_run: bool):
    """关注"""
    if dry_run:
        print(f"   [DRY RUN] 👤 不实际关注")
        return
    await client.follow_user(user_id)
    print(f"   👤 已关注")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  主流程
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def auto_post_scheduler(client: Client, llm: AsyncOpenAI):
    """自动发帖调度器: 每天 POST_TIMES 时间点发推"""
    if not ENABLE_AUTO_POST:
        return
    posted_today = set()
    last_date = None

    while True:
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        current_time = now.strftime("%H:%M")

        # 跨天清零
        if last_date != today:
            posted_today = set()
            last_date = today

        # 检查是否到发帖时间
        if current_time in POST_TIMES and current_time not in posted_today:
            posted_today.add(current_time)
            topic = random.choice(POST_TOPICS)
            print(f"\n📝 [{now.strftime('%H:%M:%S')}] 定时发帖 → 主题: {topic}")

            try:
                text = await generate_post(llm, topic)
                print(f"   推文: {text}")

                if DRY_RUN:
                    print(f"   [DRY RUN] ✋ 不实际发送")
                else:
                    await client.create_tweet(text=text)
                    print(f"   ✅ 已发送")
            except Exception as e:
                print(f"   ⚠️  发帖失败: {e}")

        # 每分钟检查一次
        await asyncio.sleep(60)


async def auto_follow_back_loop(client: Client):
    """自动回关: 检查关注我的人, 自动回关"""
    if not ENABLE_AUTO_FOLLOW_BACK:
        return

    while True:
        try:
            me = await client.user()
            print(f"\n👥 [{datetime.now().strftime('%H:%M:%S')}] 检查新粉丝...")

            followers = await me.get_followers(count=50)
            follow_back_count = 0
            for follower in followers:
                try:
                    await client.follow_user(str(follower.id))
                    follow_back_count += 1
                    print(f"   ✅ 已回关 @{follower.screen_name}")
                    await short_delay(5, 15)
                    if follow_back_count >= 5:  # 每轮最多回关 5 个
                        break
                except Exception:
                    continue

            if follow_back_count == 0:
                print(f"   本轮无新粉丝需要回关")

        except Exception as e:
            print(f"   ⚠️  回关检查出错: {e}")

        await asyncio.sleep(1800)  # 每 30 分钟检查一次


async def main():
    print("🚀 Twitter 拟人 Bot v2 启动 (全功能版)")
    print(f"   模式: {'🟡 DRY RUN (只打印不发)' if DRY_RUN else '🟢 LIVE (实际发送)'}")
    print(f"   监控标签: {WATCH_HASHTAGS}")
    print(f"   速率限制: 评论 {MAX_REPLIES_PER_HOUR}/h · 点赞 {MAX_LIKES_PER_HOUR}/h · 关注 {MAX_FOLLOWS_PER_HOUR}/h")
    print(f"   行为概率: 评论 {PROB_COMMENT*100:.0f}% · 点赞 {PROB_LIKE*100:.0f}% · 关注 {PROB_FOLLOW*100:.0f}%")
    print(f"   自动发帖: {'✅ ' + str(POST_TIMES) if ENABLE_AUTO_POST else '❌'}")
    print(f"   自动回关: {'✅' if ENABLE_AUTO_FOLLOW_BACK else '❌'}")
    print(f"   LLM: {LLM_PROVIDER} / {LLM_MODEL}")
    print("─" * 55)

    memory.init_db()
    print(f"✅ 记忆数据库就绪 ({memory.DB_PATH})")

    client = Client('en-US')

    if os.path.exists(COOKIES_FILE):
        client.load_cookies(COOKIES_FILE)
        me = await client.user()
        print(f"✅ Twitter 登录成功 @{me.screen_name} (从 cookie)")
    else:
        if not all([TWITTER_USERNAME, TWITTER_EMAIL, TWITTER_PASSWORD]):
            print("❌ 缺少 Twitter 账号信息！请在 .env 里填入")
            return
        print(f"🔑 首次登录 @{TWITTER_USERNAME} ...")
        await client.login(
            auth_info_1=TWITTER_USERNAME,
            auth_info_2=TWITTER_EMAIL,
            password=TWITTER_PASSWORD,
        )
        client.save_cookies(COOKIES_FILE)
        me = await client.user()
        print(f"✅ 登录成功 @{me.screen_name}")

    if not LLM_API_KEY:
        print("❌ 缺少 LLM_API_KEY！请在 .env 里填入")
        return
    llm = AsyncOpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
    print(f"✅ LLM 客户端已就绪 ({LLM_MODEL})")
    print("─" * 55)

    # 启动后台任务
    tasks = []
    if ENABLE_AUTO_POST:
        tasks.append(asyncio.create_task(auto_post_scheduler(client, llm)))
    if ENABLE_AUTO_FOLLOW_BACK:
        tasks.append(asyncio.create_task(auto_follow_back_loop(client)))
    print(f"✅ 后台任务已启动: {len(tasks)} 个 (自动发帖 + 自动回关)")

    # 三种速率计数器 + 行为分类
    counts = {"comment": 0, "like": 0, "follow": 0}
    limits = {
        "comment": MAX_REPLIES_PER_HOUR,
        "like":    MAX_LIKES_PER_HOUR,
        "follow":  MAX_FOLLOWS_PER_HOUR,
    }
    hour_reset_time = time.time()
    interacted_ids = set()    # 所有动作过 (避免重复)
    cycle = 0

    while True:
        cycle += 1
        if time.time() - hour_reset_time > 3600:
            counts = {k: 0 for k in counts}
            hour_reset_time = time.time()
            print(f"\n⏰ 每小时计数重置")

        if all(counts[k] >= limits[k] for k in counts):
            wait = (3600 - (time.time() - hour_reset_time)) / 60
            print(f"\n⏸️  所有动作都到上限, 等 {wait:.0f} 分钟")
            await asyncio.sleep(600)
            continue

        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🔄 第 {cycle} 轮扫描")
        scanned_any = False

        for tag in WATCH_HASHTAGS:
            try:
                print(f"\n🔍 扫描 #{tag}")
                tweets = await client.search_tweet(tag, 'Latest', count=10)

                for tweet in tweets:
                    if tweet.id in interacted_ids:
                        continue
                    if tweet.user is None:
                        continue

                    text = tweet.text
                    user = tweet.user.screen_name
                    user_id = str(tweet.user.id)

                    if len(text) < 20:
                        continue
                    if "http" in text:
                        continue
                    if text.startswith("RT @"):
                        continue
                    if text.startswith("@"):
                        continue

                    interacted_ids.add(tweet.id)
                    scanned_any = True

                    print(f"\n   📝 @{user}: {text[:120]}...")

                    # ── 行为多样性: 决定做什么动作 ──
                    action = choose_action()
                    if counts[action] >= limits[action]:
                        # 这个动作到上限了, 降级到 comment
                        if counts["comment"] < limits["comment"]:
                            action = "comment"
                        else:
                            continue
                    print(f"   🎯 行为: {action}")

                    # ── 评论 ──
                    if action == "comment":
                        memory.upsert_user(user_id, user)
                        user_ctx = memory.get_user_context(user_id)
                        print(f"   🧠 记忆: {user_ctx.get('reply_count', 0)} 次对话")

                        try:
                            reply = await generate_reply(llm, text, user, user_ctx)
                            print(f"   🤖 AI 回复: {reply}")
                        except Exception as e:
                            print(f"   ⚠️  LLM 出错: {e}")
                            continue

                        await humanize_delay(30, 120)
                        await reply_to_tweet(tweet, reply, DRY_RUN)
                        memory.save_reply(user_id, text, reply)
                        counts["comment"] += 1

                    # ── 点赞 ──
                    elif action == "like":
                        await like_tweet(client, str(tweet.id), DRY_RUN)
                        await short_delay(5, 20)
                        counts["like"] += 1

                    # ── 关注作者 ──
                    elif action == "follow":
                        await follow_user(client, user_id, DRY_RUN)
                        await short_delay(10, 30)
                        counts["follow"] += 1

                    if all(counts[k] >= limits[k] for k in counts):
                        break

                if all(counts[k] >= limits[k] for k in counts):
                    break

            except Exception as e:
                print(f"   ❌ 扫描 #{tag} 出错: {e}")
                await asyncio.sleep(30)
                continue

        if not scanned_any:
            print(f"\n   本轮无符合条件的新推文")

        summary = " · ".join(f"{k} {counts[k]}/{limits[k]}" for k in counts)
        print(f"\n💤 下一轮 {SCAN_INTERVAL_SEC} 秒后... [{summary}]")
        await asyncio.sleep(SCAN_INTERVAL_SEC)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="LIVE 模式 (默认 DRY_RUN)")
    args = parser.parse_args()

    if args.live:
        DRY_RUN = False

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 已退出 (Ctrl+C)")
    except Exception as e:
        print(f"\n\n❌ 致命错误: {e}")
        raise