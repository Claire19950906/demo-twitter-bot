"""
多账号调度器
═══════════════════════════════════════════════════════════════
用法:
  python multi_bot.py                     # 读 accounts.yaml 跑所有账号
  python multi_bot.py --account tech      # 只跑 tech_account

每个账号独立:
  - cookie 文件
  - memory 数据库
  - 速率限制
  - LLM 配置 (共用, 但 prompt 不同)
  - 启动时间错开 (防被识别为批量号)
"""

import asyncio
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    print("❌ 需要 PyYAML: pip install pyyaml")
    sys.exit(1)


ACCOUNTS_FILE = Path("accounts.yaml")


def load_accounts() -> dict:
    """读 accounts.yaml"""
    if not ACCOUNTS_FILE.exists():
        print(f"❌ 没找到 {ACCOUNTS_FILE}")
        print("   cp accounts.yaml.example accounts.yaml")
        sys.exit(1)
    with open(ACCOUNTS_FILE) as f:
        return yaml.safe_load(f)


async def run_single_account(account_cfg: dict, global_cfg: dict, schedule: dict, dry_run: bool = True):
    """跑单个账号 (简单包装, 实际还是调 bot.py 的 main)"""
    name = account_cfg["name"]
    print(f"\n{'='*60}")
    print(f"🤖 启动账号: {name} ({account_cfg['username']})")
    print(f"{'='*60}\n")

    # 这里用 monkey-patch 的方式导入 main, 改它的全局变量
    import bot
    import memory

    # 改 bot 模块的配置
    bot.WATCH_HASHTAGS = account_cfg["hashtags"]
    bot.SYSTEM_PROMPT = account_cfg["system_prompt"]
    bot.MAX_REPLIES_PER_HOUR = account_cfg["limits"]["comment"]
    bot.MAX_LIKES_PER_HOUR = account_cfg["limits"]["like"]
    bot.MAX_FOLLOWS_PER_HOUR = account_cfg["limits"]["follow"]
    bot.POST_TOPICS = account_cfg.get("post_topics", [])
    bot.SCAN_INTERVAL_SEC = schedule.get("scan_interval_sec", 180)
    bot.DRY_RUN = dry_run or global_cfg.get("dry_run", True)

    # 改 memory 模块的 DB 路径
    memory.DB_PATH = Path(account_cfg["memory_db"])

    # 跑
    try:
        await bot.main()
    except Exception as e:
        print(f"❌ 账号 {name} 出错: {e}")


async def run_all():
    """读配置, 启动所有账号 (每个账号一个 task)"""
    cfg = load_accounts()
    accounts = cfg["accounts"]
    global_cfg = cfg.get("global", {})
    schedule = cfg.get("schedule", {})
    startup_interval = schedule.get("startup_interval_sec", 300)

    print(f"\n📋 配置: {len(accounts)} 个账号")
    for a in accounts:
        print(f"   - {a['name']} ({a['username']}): {len(a['hashtags'])} tags")
    print(f"   错开启动: 每 {startup_interval}s")
    print(f"   模式: {'DRY_RUN' if global_cfg.get('dry_run', True) else 'LIVE'}\n")

    # 单账号模式
    if "--account" in sys.argv:
        idx = sys.argv.index("--account")
        target_name = sys.argv[idx + 1]
        target = next((a for a in accounts if a["name"] == target_name), None)
        if not target:
            print(f"❌ 没找到账号: {target_name}")
            return
        await run_single_account(target, global_cfg, schedule, dry_run=True)
        return

    # 全账号模式: 错开启动
    tasks = []
    for i, acc in enumerate(accounts):
        if i > 0:
            print(f"\n⏳ 等 {startup_interval}s 启动下一个账号...\n")
            await asyncio.sleep(startup_interval)
        task = asyncio.create_task(
            run_single_account(acc, global_cfg, schedule, dry_run=global_cfg.get("dry_run", True))
        )
        tasks.append(task)

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    try:
        asyncio.run(run_all())
    except KeyboardInterrupt:
        print("\n\n👋 多账号 Bot 已退出 (Ctrl+C)")
    except Exception as e:
        print(f"\n\n❌ 致命错误: {e}")
        raise