# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [4.0.0] - 2026-09-20 — Production Ready

### ✨ New Features (v4 additions)

- **A/B Testing** (`ab_test.py`): 4 prompt variants with weighted random assignment, sticky per-user ID, 4 outcome metrics (comment_sent, replied, liked_back, followed_back)
- **Webhook Notifications** (`notifier.py`): Concurrent Slack / DingTalk / WeCom / Telegram alerts via `asyncio.gather()`. Zero-config when `.env` empty.
- **Quality Monitoring** (`quality.py`): LLM repetition detection, API error spike alert, Twitter rate-limit wall detection, automatic degradation buffer

### 🆕 v3 features (still in v4)

- Smart 4-dimension tweet scoring (`analyzer.py`)
- Streamlit WebUI dashboard with 6 tabs (`dashboard.py`)
- Multi-account scheduler (`multi_bot.py` + `accounts.yaml`)
- Telegram adapter (`telegram_bot.py`)
- Auto image generation (DALL-E 3, `image_gen.py`)
- One-click launcher with Docker awareness (`start.sh`)
- Dockerfile + docker-compose (bot + dashboard + telegram profile)

### 📝 Documentation

- LICENSE (MIT + disclaimer)
- SECURITY.md
- CONTRIBUTING.md
- Issue / Feature / PR templates
- GitHub Actions CI (Ubuntu + macOS × Python 3.10/3.11/3.12)

### Stats

- **10 Python modules**, **3145+ lines**
- **26 files**, 3 commits

---

## [3.0.0] - 2026-09-15 — Productization

- 4-dim scoring + behavior diversity
- Streamlit dashboard (5 tabs)
- Multi-account
- Telegram adapter
- Auto image
- One-click start

Stats: 6 modules, 2086 lines

---

## [2.0.0] - 2026-09-10 — Full Features

- Behavior diversity (65/25/10 split)
- Auto post scheduler (9:30/14:00/21:30)
- Auto follow-back loop
- Long-term SQLite memory
- Typo injection (less "perfect" output)

Stats: 663 lines

---

## [1.0.0] - 2026-09-01 — MVP

- twikit login
- LLM-powered reply
- Rate limits

Stats: 270 lines

[4.0.0]: https://github.com/Claire19950906/demo-twitter-bot/releases/tag/v4.0.0