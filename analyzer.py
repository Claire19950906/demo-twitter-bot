"""
数据分析 + 智能打分
═══════════════════════════════════════════════════════════════
功能:
  - 数据库扩展: 新增 tweet_log / action_log / daily_stats 3 张表
  - 推文多维度评分 (关键词 / 作者历史 / 互动信号 / 长度)
  - 智能筛选: 高分评论 / 中分点赞 / 低分跳过
  - 日志记录 + 报表 API (供 dashboard.py 调用)
"""

import re
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path

from memory import DB_PATH  # 复用 memory 模块的同一个 DB


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  关键词词典 (按你的垂类调)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 你感兴趣的关键词 (含 → 加分)
KEYWORDS_POSITIVE = [
    "AI", "LLM", "GPT", "Claude", "agent", "automation",
    "产品", "创业", "独立开发", "MVP", "增长",
    "AI 工具", "GPT", "RAG", "prompt",
    "产品经理", "营销", "内容", "创作",
    "indiehacker", "buildinpublic", "ship",
]

# 你不想回的关键词 (含 → 减分 / 跳过)
KEYWORDS_NEGATIVE = [
    "招聘", "求职", "内推", "拉群",
    "股票", "币圈", "区块链", "NFT",
    "广告", "打折", "优惠", "促销",
]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  数据库扩展 (在 memory.DB_PATH 上加 3 张表)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def extend_db():
    """扩展数据库: 新增 3 张表 + 索引 (不破坏 memory.py 的 users/replies)"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tweet_log (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                tweet_id   TEXT,
                text       TEXT,
                author     TEXT,
                hashtag    TEXT,
                score      REAL,
                action     TEXT,
                created_at REAL
            );

            CREATE TABLE IF NOT EXISTS action_log (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    TEXT,
                target_id  TEXT,
                action     TEXT,
                hashtag    TEXT,
                created_at REAL
            );

            CREATE TABLE IF NOT EXISTS daily_stats (
                date       TEXT PRIMARY KEY,
                comments   INTEGER DEFAULT 0,
                likes      INTEGER DEFAULT 0,
                follows    INTEGER DEFAULT 0,
                posts      INTEGER DEFAULT 0,
                reach      INTEGER DEFAULT 0,
                avg_score  REAL DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_tweet_log_created ON tweet_log(created_at);
            CREATE INDEX IF NOT EXISTS idx_action_log_created ON action_log(created_at);
            CREATE INDEX IF NOT EXISTS idx_action_log_user    ON action_log(user_id);
        """)
        print("✅ 分析数据库表就绪 (tweet_log / action_log / daily_stats)")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  4 维打分 (0-1 分)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def score_keyword_match(text: str) -> float:
    """维度 1: 关键词匹配 (0-1)"""
    text_lower = text.lower()
    pos_hits = sum(1 for kw in KEYWORDS_POSITIVE if kw.lower() in text_lower)
    neg_hits = sum(1 for kw in KEYWORDS_NEGATIVE if kw.lower() in text_lower)
    pos_score = min(pos_hits / 3, 1.0) * 0.7
    neg_penalty = min(neg_hits, 2) * 0.3
    return max(0.0, min(1.0, pos_score - neg_penalty))


def score_author_history(author: str) -> float:
    """维度 2: 作者历史 (0-1)"""
    with sqlite3.connect(DB_PATH) as conn:
        cnt = conn.execute(
            "SELECT COUNT(*) FROM action_log WHERE user_id=?",
            (author,),
        ).fetchone()[0] or 0
    if cnt == 0:
        return 0.4
    if cnt >= 5:
        return 0.9
    return min(0.5 + cnt * 0.1, 0.8)


def score_engagement_hints(text: str) -> float:
    """维度 3: 互动信号 (0-1)"""
    s = 0.0
    if "?" in text or "？" in text:
        s += 0.4
    if any(w in text for w in ["想听听", "求建议", "求教", "大家觉得", "怎么选"]):
        s += 0.3
    if any(w in text.lower() for w in ["ship", "launch", "刚发", "刚上", "刚做"]):
        s += 0.2
    if any(w in text for w in ["求赞", "求 RT", "求关注", "互赞"]):
        s -= 0.5
    return max(0.0, min(1.0, s))


def score_length_quality(text: str) -> float:
    """维度 4: 长度质量 (0-1)"""
    n = len(text)
    if n < 20: return 0.1
    if 50 <= n <= 200: return 1.0
    if 20 <= n < 50: return 0.5 + (n - 20) / 30 * 0.5
    if 200 < n <= 300: return 1.0 - (n - 200) / 100 * 0.5
    return 0.3


def score_tweet(text: str, author: str) -> dict:
    """综合打分, 返回详情"""
    s1 = score_keyword_match(text)
    s2 = score_author_history(author)
    s3 = score_engagement_hints(text)
    s4 = score_length_quality(text)
    total = round(s1 * 0.3 + s2 * 0.3 + s3 * 0.2 + s4 * 0.2, 3)
    return {"total": total, "keyword": round(s1, 3), "author": round(s2, 3),
            "engagement": round(s3, 3), "length": round(s4, 3)}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  智能筛选: score → action
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def decide_action(score: float, current_counts: dict, limits: dict) -> str | None:
    """根据分数决定动作, 受速率限制
    - score >= 0.6 → comment
    - 0.4 <= score < 0.6 → like
    - score < 0.4 → 跳过
    """
    if score >= 0.6:
        preferred = "comment"
    elif score >= 0.4:
        preferred = "like"
    else:
        return None
    if current_counts.get(preferred, 0) < limits.get(preferred, 0):
        return preferred
    # 降级
    fallback = {"comment": "like"}
    fb = fallback.get(preferred)
    if fb and current_counts.get(fb, 0) < limits.get(fb, 0):
        return fb
    return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  日志记录
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def log_tweet(tweet_id, text, author, hashtag, score, action):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO tweet_log (tweet_id, text, author, hashtag, score, action, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (tweet_id, text[:500], author, hashtag, score, action, time.time()),
        )


def log_action(user_id, target_id, action, hashtag=""):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO action_log (user_id, target_id, action, hashtag, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, target_id, action, hashtag, time.time()),
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  报表 API (供 dashboard 用)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_today_stats() -> dict:
    today = datetime.now().strftime("%Y-%m-%d")
    start = datetime.now().replace(hour=0, minute=0, second=0).timestamp()

    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT action, COUNT(*) FROM action_log WHERE created_at >= ? GROUP BY action",
            (start,),
        ).fetchall()
        counts = dict(rows)

        avg_score = round(conn.execute(
            "SELECT AVG(score) FROM tweet_log WHERE created_at >= ?",
            (start,)).fetchone()[0] or 0, 3)
        scanned = conn.execute(
            "SELECT COUNT(*) FROM tweet_log WHERE created_at >= ?",
            (start,)).fetchone()[0] or 0
        reach = conn.execute(
            "SELECT COUNT(DISTINCT user_id) FROM action_log WHERE created_at >= ?",
            (start,)).fetchone()[0] or 0

        # cache
        conn.execute(
            "INSERT OR REPLACE INTO daily_stats "
            "(date, comments, likes, follows, posts, reach, avg_score) "
            "VALUES (?, ?, ?, ?, COALESCE((SELECT posts FROM daily_stats WHERE date=?), 0), ?, ?)",
            (today, counts.get("comment", 0), counts.get("like", 0),
             counts.get("follow", 0), today, reach, avg_score),
        )

    return {"date": today, "comments": counts.get("comment", 0),
            "likes": counts.get("like", 0), "follows": counts.get("follow", 0),
            "scanned": scanned, "reach": reach, "avg_score": avg_score}


def get_top_users(limit: int = 20) -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("""
            SELECT user_id, COUNT(*) as cnt,
                   SUM(CASE WHEN action='comment' THEN 1 ELSE 0 END) as comments
            FROM action_log GROUP BY user_id ORDER BY cnt DESC LIMIT ?
        """, (limit,)).fetchall()
    return [{"user_id": r[0], "total": r[1], "comments": r[2]} for r in rows]


def get_hashtag_performance() -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("""
            SELECT hashtag, COUNT(*), AVG(score),
                   SUM(CASE WHEN action='comment' THEN 1 ELSE 0 END)
            FROM tweet_log WHERE hashtag IS NOT NULL AND hashtag != ''
            GROUP BY hashtag ORDER BY COUNT(*) DESC
        """).fetchall()
    return [{"hashtag": r[0], "count": r[1], "avg_score": round(r[2] or 0, 3),
             "comments": r[3] or 0} for r in rows]


def get_recent_replies(limit: int = 50) -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("""
            SELECT r.user_id, m.screen_name, r.original_text, r.reply_text, r.created_at
            FROM replies r LEFT JOIN users m ON r.user_id = m.user_id
            ORDER BY r.created_at DESC LIMIT ?
        """, (limit,)).fetchall()
    return [{"user_id": r[0], "name": r[1], "original": r[2],
             "reply": r[3], "time": datetime.fromtimestamp(r[4]).strftime("%m-%d %H:%M")}
            for r in rows]


def get_weekly_trend() -> list[dict]:
    result = []
    for i in range(6, -1, -1):
        day = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute(
                "SELECT comments, likes, follows, reach FROM daily_stats WHERE date=?",
                (day,)).fetchone()
        if row:
            result.append({"date": day[5:], "comments": row[0], "likes": row[1],
                           "follows": row[2], "reach": row[3]})
        else:
            result.append({"date": day[5:], "comments": 0, "likes": 0,
                           "follows": 0, "reach": 0})
    return result