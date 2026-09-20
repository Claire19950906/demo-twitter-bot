"""
记忆 + 拟人化增强模块
═══════════════════════════════════════════════════════════════
提供:
  - SQLite 长期记忆 (每个用户的对话历史)
  - 用户画像生成 (LLM 分析对方风格)
  - 错别字注入 (随机替换, 每 N 条加 1 个)
  - 个性化回复 (根据画像调整语气)
"""

import random
import sqlite3
import time
from pathlib import Path


DB_PATH = Path("bot_memory.db")


def init_db():
    """初始化数据库 (用户表 + 对话表)"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id       TEXT PRIMARY KEY,
                username      TEXT,
                first_seen    REAL,
                last_reply    REAL,
                reply_count   INTEGER DEFAULT 0,
                style_notes   TEXT DEFAULT '',
                topics        TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS replies (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       TEXT,
                tweet_text    TEXT,
                reply_text    TEXT,
                created_at    REAL
            );
        """)


def upsert_user(user_id: str, username: str):
    """记录或更新用户"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO users (user_id, username, first_seen)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                last_reply = excluded.last_reply
        """, (user_id, username, time.time()))


def get_user_context(user_id: str) -> dict:
    """读取用户上下文"""
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("""
            SELECT username, reply_count, style_notes, topics
            FROM users WHERE user_id = ?
        """, (user_id,)).fetchone()
        if not row:
            return {"known": False, "reply_count": 0}

        recent = conn.execute("""
            SELECT reply_text FROM replies
            WHERE user_id = ? ORDER BY created_at DESC LIMIT 3
        """, (user_id,)).fetchall()
        recent_texts = [r[0] for r in recent]

        return {
            "known": True,
            "username": row[0],
            "reply_count": row[1],
            "style_notes": row[2] or "",
            "topics": row[3] or "",
            "recent_replies": recent_texts,
        }


def save_reply(user_id: str, tweet_text: str, reply_text: str):
    """保存一条回复记录"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO replies (user_id, tweet_text, reply_text, created_at)
            VALUES (?, ?, ?, ?)
        """, (user_id, tweet_text, reply_text, time.time()))
        conn.execute("""
            UPDATE users SET
                reply_count = reply_count + 1,
                last_reply = ?
            WHERE user_id = ?
        """, (time.time(), user_id))


def update_user_profile(user_id: str, style_notes: str, topics: str):
    """LLM 分析后回写用户画像"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            UPDATE users SET style_notes = ?, topics = ?
            WHERE user_id = ?
        """, (style_notes, topics, user_id))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  用户画像分析 (LLM 二次调用)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ANALYZE_PROMPT = """分析这个 Twitter 用户的风格（极简, 30字以内）:

对方最近的推文:
{tweets}

对方与我的对话历史:
{history}

输出格式（两行, 不要其他）:
风格: [ta 喜欢用什么语气, 关注什么话题]
话题: [ta 关心什么话题, 可以用什么共同语言]"""


async def analyze_user(llm, user_id: str, recent_tweets: list, history: list) -> tuple:
    """用 LLM 分析用户风格, 返回 (style_notes, topics)"""
    tweets_text = "\n".join(f"- {t}" for t in recent_tweets[:3]) or "(无)"
    history_text = "\n".join(f"- 我: {h}" for h in history[:3]) or "(无)"

    try:
        resp = await llm.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": ANALYZE_PROMPT.format(
                tweets=tweets_text, history=history_text
            )}],
            temperature=0.3,
            max_tokens=100,
        )
        text = resp.choices[0].message.content.strip()
        style, topics = "", ""
        for line in text.split("\n"):
            if line.startswith("风格:"):
                style = line.replace("风格:", "").strip()
            elif line.startswith("话题:"):
                topics = line.replace("话题:", "").strip()
        return style, topics
    except Exception as e:
        print(f"   ⚠️  用户画像分析失败: {e}")
        return "", ""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  错别字注入 (拟人化关键)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 形近字替换表 (中文输入法常见错按)
TYPO_MAP = {
    '的': ['得', '地'],
    '得': ['的', '地'],
    '地': ['的', '得'],
    '在': ['再'],
    '再': ['在'],
    '做': ['作'],
    '作': ['做'],
    '像': ['象'],
    '象': ['像'],
    '啊': ['阿'],
    '吧': ['八'],
    '我': ['哦'],
    '你': ['泥'],
    '了': ['啦', '喇'],
    '有': ['由'],
    '是': ['四'],
    '人': ['入'],
    '能': ['呢'],
    '好': ['号'],
}


def maybe_inject_typo(text: str, prob: float = 0.08) -> str:
    """以 prob 概率注入 1 个错别字"""
    if random.random() > prob:
        return text

    chars = list(text)
    candidates = [i for i, c in enumerate(chars) if c in TYPO_MAP]
    if not candidates:
        return text

    i = random.choice(candidates)
    chars[i] = random.choice(TYPO_MAP[chars[i]])
    return ''.join(chars)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  个性化系统提示词 (注入上下文)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_system_prompt(base: str, user_ctx: dict) -> str:
    """根据用户上下文生成动态 system prompt"""
    if not user_ctx.get("known"):
        return base

    extra = []
    if user_ctx.get("reply_count", 0) > 0:
        extra.append(
            f"\n注意: 你之前和 @{user_ctx['username']} 互动过 {user_ctx['reply_count']} 次。"
            f"这次回复要和之前有点连贯感。")
    if user_ctx.get("style_notes"):
        extra.append(f"\n对方风格: {user_ctx['style_notes']}")
    if user_ctx.get("topics"):
        extra.append(f"\n共同话题: {user_ctx['topics']}")
    if user_ctx.get("recent_replies"):
        recent = " / ".join(user_ctx['recent_replies'][:3])
        extra.append(f"\n你之前回过 ta: {recent}")

    return base + "".join(extra)