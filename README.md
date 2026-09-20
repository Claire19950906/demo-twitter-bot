# Twitter/X 拟人自动互动 Bot v4（产品级 + Docker）

<!-- Badges (push to GitHub 后自动生效; 替换 <USER>/<REPO> 为你的地址) -->
[![CI](https://github.com/<USER>/<REPO>/actions/workflows/ci.yml/badge.svg)](https://github.com/<USER>/<REPO>/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](Dockerfile)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

> 给机械脚本接上 LLM，让它"带脑子"自动拟人互动。
> 完整产品级：智能打分 · 行为多样性 · 数据分析 · WebUI · 多账号 · Telegram · 自动发图 · A/B 测试 · 质量监控 · Webhook 报警 · Docker 部署。
>
> 走的是 **twikit 爬虫**（不需要 API key）+ **DeepSeek/ChatGPT LLM** 路线，10 元钱 / 月跑得动。

> ⚠️ **DISCLAIMER**: Use a **burner account**, not your personal Twitter account. See [SECURITY.md](SECURITY.md).

## 🎯 它能干什么（v4 全功能）

### 核心 (v1-v2)
| 模块 | 做什么 |
|------|--------|
| 🎯 **智能打分** | 4 维评分（关键词 / 作者历史 / 互动信号 / 长度），跳过低质推文 |
| 🎲 **行为多样性** | 看到推文 → 65% 评论 / 25% 点赞 / 10% 关注作者 |
| 💬 **拟人化评论** | LLM 读懂推文 + 长期记忆注入 + 错别字 + 高斯延迟 30-120s |
| ❤️ **自动点赞** | 中分推文静默点赞 |
| 👤 **自动关注** | 有意思的作者自动 follow |
| 📝 **自动发帖** | 每天 9:30/14:00/21:30 定时发推 |
| 🔄 **自动回关** | 关注你的人 → 自动 follow back（每 30 分钟）|
| 🧠 **长期记忆** | SQLite 存你和每个用户的对话历史 + 画像 |
| ✏️ **错别字** | 8% 概率随机替换形近字，更像真人 |
| 🛡️ **DRY_RUN** | 默认只打印不真发，调试安全 |

### 产品化 (v3)
| 模块 | 做什么 |
|------|--------|
| 📊 **数据分析** | 评分/动作/触达全记 SQLite，按 hashtag / 作者统计 |
| 🌐 **WebUI** | Streamlit Dashboard 实时看数据 (6 个 tab) |
| 👥 **多账号** | YAML 配置，每个账号独立人设/速率/记忆 |
| ✈️ **Telegram** | 一键搬到 Telegram，自动回复消息 |
| 🖼️ **自动发图** | LLM 同时生成文案 + 配图描述 + DALL-E 3 生图 |
| 🚀 **一键启动** | `./start.sh {dry\|live\|stop\|status\|logs}` |

### 增长 (v4)
| 模块 | 做什么 |
|------|--------|
| 🧪 **A/B 测试** | 4 种 Prompt 风格对比，自动找最优人设 |
| 📢 **Webhook 通知** | Slack/钉钉/企业微信/Telegram 报警 + 日报 |
| ⚠️ **质量监控** | LLM 重复检测 / API 错误突增 / 速率撞墙 |
| 🐳 **Docker** | `docker compose up -d` 一行命令全起 |

## 📦 你需要的

1. **Python 3.10+**（或 Docker）
2. **Twitter 小号**（必须！主号被封 = 一切没了）
3. **DeepSeek API Key**（10 元够用一个月，[注册](https://platform.deepseek.com/)）
4. （可选）OpenAI Key（发图 / 用 GPT）
5. （可选）Telegram Bot Token（[找 @BotFather](https://t.me/BotFather)）
6. （可选）任意 Webhook URL（Slack/钉钉/企业微信）

## 🚀 方式一：Docker（推荐）

```bash
cd /Users/claire/.cline/data/workspaces/chat/social-ai-tools/demo-twitter-bot

cp .env.example .env
# 编辑 .env, 填 TWITTER_USERNAME / TWITTER_PASSWORD / LLM_API_KEY

# 一行命令全起 (bot + dashboard)
docker compose up -d

# 看日志
docker compose logs -f bot
docker compose logs -f dashboard

# 加 Telegram
docker compose --profile telegram up -d

# 停
docker compose down

# 进容器
docker compose exec bot bash
```

打开 http://localhost:8501 看 Dashboard。

## 🚀 方式二：本地 Python

```bash
cd /Users/claire/.cline/data/workspaces/chat/social-ai-tools/demo-twitter-bot

pip install -r requirements.txt
cp .env.example .env
# 编辑 .env

./start.sh                # DRY_RUN 模式 (安全)
```

新终端：
```bash
streamlit run dashboard.py  # WebUI
python multi_bot.py        # 多账号
python telegram_bot.py     # Telegram
```

## 📋 Dashboard 6 个 tab

- 📊 **总览** — 今日/本周互动量 + 图表
- 👥 **用户** — Top 互动用户
- 💬 **评论** — 最近 AI 生成的 50 条评论
- 🎯 **表现** — hashtag 效果排行
- 🧪 **A/B 测试** — 4 种 Prompt 回复率对比 + ⭐ 最佳 variant
- 📜 **日志** — 实时日志 tail

## 🧪 A/B 测试 4 种 Prompt

预置 4 种人设风格，自动分配给新用户，同用户固定 prompt：

| Variant | 风格 |
|---------|-----|
| A_专业派 | 产品视角，尖锐问题 |
| B_活泼派 | 热情有 emoji |
| C_吐槽派 | 毒舌，黑色幽默 |
| D_共情派 | 温和，鼓励小作者 |

Dashboard 自动展示回复率排行 + ⭐ 标记最佳，手动调 `weight` 控制流量分配。

## 📢 Webhook 报警

`.env` 加任意一个，自动启用：
```
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
DINGTALK_WEBHOOK_URL=https://oapi.dingtalk.com/robot/send?access_token=...
WECOM_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=...
TELEGRAM_NOTIFY_CHAT_ID=123456789  # 复用 TELEGRAM_BOT_TOKEN
```

```python
from notifier import notify_error, notify_daily_summary
await notify_error("🚨 Bot 出错", "API 错误率 80%")
await notify_daily_summary(stats)  # 晚上 21:00 推日报
```

## 📂 文件清单 (v4 完整版)

```
demo-twitter-bot/                            2566+ 行
├── 核心 (v1-v2)
│   ├── bot.py              17 KB / 461 行    Twitter 主脚本
│   ├── memory.py           7.5 KB / 213 行   长期记忆
│   └── start.sh            4.4 KB / 152 行   一键启动 (含 Docker 适配)
│
├── 产品化 (v3)
│   ├── analyzer.py         12 KB / 283 行   智能打分 + 数据分析
│   ├── dashboard.py        6.6 KB / 211 行   Streamlit WebUI
│   ├── multi_bot.py        3.9 KB / 118 行   多账号调度
│   ├── telegram_bot.py     8.1 KB / 227 行   Telegram 版
│   ├── image_gen.py        5.5 KB / 152 行   自动发图
│   └── accounts.yaml.example              多账号配置模板
│
├── 增长 (v4)
│   ├── ab_test.py          7.5 KB / 190 行   A/B 测试 Prompt
│   ├── notifier.py         3.5 KB / 107 行   Webhook 多渠道
│   ├── quality.py          5.2 KB / 133 行   质量监控
│   ├── Dockerfile                          Docker 镜像
│   ├── docker-compose.yml                  一键全起
│   └── .dockerignore
│
└── 配置
    ├── .env.example
    ├── requirements.txt   (twikit+openai+streamlit+aiohttp+httpx+pyyaml)
    ├── .gitignore
    └── README.md
```

## 🎛️ 调参指南

### bot.py 顶部
```python
WATCH_HASHTAGS = [...]
PROB_COMMENT/LIKE/FOLLOW = 0.65/0.25/0.10
MAX_REPLIES_PER_HOUR = 3
MAX_LIKES_PER_HOUR = 8
MAX_FOLLOWS_PER_HOUR = 2
ENABLE_AUTO_POST = True
POST_TIMES = ["09:30", "14:00", "21:30"]
SYSTEM_PROMPT = "你是..."
```

### analyzer.py 关键词词典
```python
KEYWORDS_POSITIVE = ["AI", "LLM", "产品", ...]
KEYWORDS_NEGATIVE = ["招聘", "股票", ...]
```

### ab_test.py 4 种 Prompt
```python
PROMPT_VARIANTS = {
    "A_专业派": {"text": "...", "weight": 1.0},
    "B_活泼派": {"text": "...", "weight": 1.0},
    ...
}
# weight 越高被选中概率越大
```

### 改人设（最常用）
直接改 `bot.py` 的 `SYSTEM_PROMPT`，保存即生效（不需重启）。

## 🔐 账号安全

| 风险 | 缓解 |
|------|------|
| 评论太多 | 速率限制 3-5/h |
| 关注太多 | 速率限制 1-2/h |
| 发帖太密 | 3-5 条/天 |
| 内容太"完美" | 启用错别字、降温度 |
| 行为太单一 | 用行为多样性（默认开）|
| 多个账号同 IP | accounts.yaml startup_interval_sec=300 |

## 🐛 出问题

| 错误 | 排查 |
|------|------|
| Twitter login failed | 账号密码 / 二次验证 / IP 异常 |
| LLM 出错 | 检查 API key / DeepSeek 余额 |
| Could not find field: variants | twikit 被反爬，等 30 秒 |
| Telegram 没响应 | 确认 Bot Token + 给 Bot 发过消息 |
| WebUI 打不开 | streamlit 装了吗？端口冲突？ |
| Docker 启动失败 | docker compose logs bot 看具体错误 |

## 📊 看效果

- **实时**：`tail -f bot.log` 或 `docker compose logs -f bot`
- **可视化**：`streamlit run dashboard.py` → http://localhost:8501
- **数据库**：`sqlite3 bot_memory.db "SELECT * FROM action_log ORDER BY created_at DESC LIMIT 20"`
- **A/B 报告**：`python -c "import ab_test; ab_test.print_report()"`