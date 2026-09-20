"""
A/B 测试模块
═══════════════════════════════════════════════════════════════
作用:
  - 多个人设 prompt 随机分配给新用户
  - 同用户固定 prompt (避免精神分裂 + 保证实验纯净)
  - 自动跟踪每个 variant 的回复率/关注率
  - 打印对比表, 支持手动调权重

用法:
  from ab_test import assign_variant, record_outcome, get_performance
  variant = assign_variant(user_id)
  prompt = get_variant_prompt(variant)
"""

import random
import sqlite3
import time

from memory import DB_PATH


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Prompt 变体 (在 ab_test.py 顶部编辑)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PROMPT_VARIANTS = {
    "A_专业派": {
        "text": """你是专业的产品经理, 关注 AI 和独立开发。
回复从产品视角出发, 问 1-2 个尖锐的产品问题。
语气专业但不严肃, 偶尔带工程师的冷幽默。
简洁, 不超过 80 字。""",
        "weight": 1.0,
    },
    "B_活泼派": {
        "text": """你是个开朗的产品经理, 喜欢尝试各种新工具。
回复热情、有活力, 经常用 emoji。
可以表达自己的使用体验, 分享踩过的坑。
自然, 像跟朋友聊天。""",
        "weight": 1.0,
    },
    "C_吐槽派": {
        "text": """你是个毒舌的产品经理, 对烂产品毫不留情。
回复犀利、直接, 偶尔带点黑色幽默。
关注产品的真实价值而不是包装。
适合评论被过度宣传的 AI 工具。""",
        "weight": 1.0,
    },
    "D_共情派": {
        "text": """你是个温和的产品经理, 喜欢鼓励独立开发者。
回复真诚, 关注对方在做的事而不是蹭流量。
适合支持小作者和新人。
语气温暖, 像资深前辈。""",
        "weight": 1.0,
    },
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  数据库扩展
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def extend_ab_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS prompt_variants (
                name TEXT PRIMARY KEY,
                text TEXT,
                weight REAL DEFAULT 1.0,
                created_at REAL
            );
            CREATE TABLE IF NOT EXISTS assignments (
                user_id TEXT PRIMARY KEY,
                variant TEXT,
                assigned_at REAL
            );
            CREATE TABLE IF NOT EXISTS variant_outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                variant TEXT,
                user_id TEXT,
                outcome TEXT,
                created_at REAL
            );
            CREATE INDEX IF NOT EXISTS idx_outcomes_variant ON variant_outcomes(variant);
        """)
        for name, cfg in PROMPT_VARIANTS.items():
            conn.execute(
                "INSERT OR IGNORE INTO prompt_variants (name, text, weight, created_at) "
                "VALUES (?, ?, ?, ?)",
                (name, cfg["text"], cfg["weight"], time.time()),
            )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  分配 + 查询
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def assign_variant(user_id: str) -> str:
    """给用户分配 variant, 同用户固定"""
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT variant FROM assignments WHERE user_id=?",
            (user_id,),
        ).fetchone()
        if row:
            return row[0]
        names = list(PROMPT_VARIANTS.keys())
        weights = [PROMPT_VARIANTS[n]["weight"] for n in names]
        variant = random.choices(names, weights=weights, k=1)[0]
        conn.execute(
            "INSERT INTO assignments (user_id, variant, assigned_at) VALUES (?, ?, ?)",
            (user_id, variant, time.time()),
        )
        return variant


def get_variant_prompt(variant_name: str) -> str:
    if variant_name in PROMPT_VARIANTS:
        return PROMPT_VARIANTS[variant_name]["text"]
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT text FROM prompt_variants WHERE name=?",
            (variant_name,),
        ).fetchone()
    return row[0] if row else ""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  效果记录 + 报表
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def record_outcome(user_id: str, outcome: str):
    """记录 outcome: comment_sent / comment_replied / liked_back / followed_back"""
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT variant FROM assignments WHERE user_id=?",
            (user_id,),
        ).fetchone()
        if not row:
            return
        conn.execute(
            "INSERT INTO variant_outcomes (variant, user_id, outcome, created_at) "
            "VALUES (?, ?, ?, ?)",
            (row[0], user_id, outcome, time.time()),
        )


def get_performance() -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        user_count = dict(conn.execute(
            "SELECT variant, COUNT(*) FROM assignments GROUP BY variant"
        ).fetchall())
        out_rows = conn.execute(
            "SELECT variant, outcome, COUNT(*) FROM variant_outcomes "
            "GROUP BY variant, outcome"
        ).fetchall()

    result = {v: {"users": user_count.get(v, 0),
                   "comments_sent": 0, "comment_replied": 0,
                   "liked_back": 0, "followed_back": 0}
              for v in PROMPT_VARIANTS}
    for v, o, c in out_rows:
        if v in result and o in result[v]:
            result[v][o] = c

    perf = []
    for v, d in result.items():
        sent, replied = d["comments_sent"], d["comment_replied"]
        perf.append({
            "variant": v, "users": d["users"],
            "comments_sent": sent, "replied": replied,
            "reply_rate": round(replied / sent, 3) if sent > 0 else 0,
            "liked_back": d["liked_back"],
            "followed_back": d["followed_back"],
        })
    perf.sort(key=lambda x: x["reply_rate"], reverse=True)
    return perf


def print_report():
    perf = get_performance()
    print("\n" + "=" * 70)
    print("🧪 A/B Test Report - Prompt 效果对比")
    print("=" * 70)
    print(f"{'Variant':<15} {'Users':>6} {'Sent':>6} {'Replied':>8} {'Reply Rate':>12}")
    print("-" * 70)
    for p in perf:
        star = " ⭐" if p["reply_rate"] == perf[0]["reply_rate"] and p["reply_rate"] > 0 else ""
        print(f"{p['variant']:<15} {p['users']:>6} {p['comments_sent']:>6} {p['replied']:>8} "
              f"{p['reply_rate']*100:>11.1f}%{star}")
    print("=" * 70 + "\n")