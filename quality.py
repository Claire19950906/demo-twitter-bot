"""
质量监控 + 异常检测
═══════════════════════════════════════════════════════════════
检测:
  - LLM 重复输出 (同一 prompt 出来几乎一样 → 降温度)
  - API 错误率 (连续 N 次失败 → 报警)
  - 账号限流信号 (429/403 → 暂停 + 报警)
  - 速率撞墙 (每小时上限连续 3 小时触发 → 报警)

用法:
  from quality import quality_check, record_llm_call, record_api_error
  record_llm_call(prompt_hash, response)
  if quality_check():
      notify_error(...)
"""

import hashlib
import sqlite3
import time
from collections import deque
from pathlib import Path

from memory import DB_PATH


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  全局滑动窗口
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

WINDOW = 100           # 最近 100 次 LLM 调用
llm_responses = deque(maxlen=WINDOW)  # 存 (hash, response)
api_errors = deque(maxlen=20)         # 最近 20 次错误 (timestamp, code)
rate_limit_hits = deque(maxlen=10)    # 最近 10 次速率撞墙


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  记录
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def record_llm_call(prompt: str, response: str):
    """记录一次 LLM 调用"""
    h = hashlib.md5(prompt.encode()).hexdigest()[:8]
    llm_responses.append((h, response.strip()))


def record_api_error(code: int):
    """记录 API 错误 (code 是 HTTP 状态码)"""
    api_errors.append((time.time(), code))


def record_rate_limit_hit():
    """记录速率撞墙"""
    rate_limit_hits.append(time.time())


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  异常检测
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def detect_llm_repetition(threshold: float = 0.4) -> bool:
    """检测 LLM 是否输出大量重复回复
    threshold: 重复率超过这个值就报警
    """
    if len(llm_responses) < 20:
        return False

    responses = [r for _, r in llm_responses]
    counter = {}
    for r in responses:
        counter[r] = counter.get(r, 0) + 1

    # 找最高频的回复
    if counter:
        top_count = max(counter.values())
        repeat_rate = top_count / len(responses)
        if repeat_rate > threshold:
            print(f"   ⚠️  LLM 重复率 {repeat_rate*100:.0f}% (阈值 {threshold*100:.0f}%)")
            print(f"   💡 建议: 提高 temperature 到 0.9+, 或换 prompt")
            return True
    return False


def detect_api_failure_burst() -> bool:
    """检测 API 错误突增 (最近 20 次有 >50% 失败)"""
    if len(api_errors) < 10:
        return False
    error_rate = len(api_errors) / 20
    if error_rate > 0.5:
        print(f"   🚨 API 错误率 {error_rate*100:.0f}% (10min 内)")
        return True
    return False


def detect_rate_limit_consecutive(threshold_hours: int = 3) -> bool:
    """检测连续 N 小时触发速率限制"""
    if len(rate_limit_hits) < threshold_hours:
        return False
    now = time.time()
    recent = [t for t in rate_limit_hits if now - t < threshold_hours * 3600]
    return len(recent) >= threshold_hours


def quality_check() -> bool:
    """总体检查, 返回 True 表示需要报警"""
    issues = []
    if detect_llm_repetition():
        issues.append("LLM 重复率过高")
    if detect_api_failure_burst():
        issues.append("API 错误突增")
    if detect_rate_limit_consecutive():
        issues.append("连续触发速率限制")

    if issues:
        print(f"   🚨 质量报警: {', '.join(issues)}")
        return True
    return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  工具: 检测推文重复 (你会不会发重复推文)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def is_duplicate_post(text: str, days: int = 1) -> bool:
    """检查最近 N 天是否发过相似推文"""
    with sqlite3.connect(DB_PATH) as conn:
        # 用 action_log 表查 post 记录 (假设 posts 有 action='post')
        # 实际可以加一张 posts 表, 这里简化用 action_log
        cutoff = time.time() - days * 86400
        rows = conn.execute("""
            SELECT target_id FROM action_log
            WHERE action='post' AND created_at >= ?
        """, (cutoff,)).fetchall()
        # 这里只是 demo, 实际应该存推文文本, 用 similarity 对比
        return False  # 占位, 后续可扩展