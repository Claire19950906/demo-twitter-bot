# Contributing to Twitter Bot

Thanks for your interest in contributing! 🎉

## 🚀 Quick Start

```bash
git clone <repo>
cd demo-twitter-bot
pip install -r requirements.txt
cp .env.example .env
# edit .env with dummy values for testing
```

Run the smoke test:
```bash
python -c "
import memory, analyzer, ab_test, quality
memory.init_db()
analyzer.extend_db()
ab_test.extend_ab_db()
quality.record_llm_call('t', 'r')
print('OK')
"
```

## 📋 Code Style

- Python: PEP 8, 4-space indent, max line length 100
- Type hints for public functions
- Docstrings for all public APIs (Google style)
- One responsibility per file/module

## 🧪 Before Submitting a PR

1. Run `python3 -m py_compile *.py` — must pass
2. Run `bash -n start.sh` — must pass
3. Update README if you change user-facing behavior
4. Add a smoke test if you add a new module

## 🎯 Areas Needing Help

- 🌐 i18n / multi-language prompts
- 🧠 Better quality monitoring (drift detection)
- 📱 Mobile-friendly dashboard (PWA)
- 🔌 New platform adapters (Mastodon, Bluesky, Threads)
- 🎨 Image generation prompts (Midjourney, SD)
- 📊 Analytics & A/B test statistics (significance testing)

## 📂 Project Structure

```
demo-twitter-bot/
├── bot.py          Twitter main script
├── analyzer.py      Scoring + analytics
├── memory.py       Long-term memory
├── dashboard.py    Streamlit WebUI
├── multi_bot.py    Multi-account
├── telegram_bot.py Telegram adapter
├── image_gen.py    Auto image
├── notifier.py     Webhook alerts
├── ab_test.py      A/B testing
├── quality.py      Quality monitoring
└── start.sh        Launcher (Docker-aware)
```

## 🤝 Code of Conduct

Be kind, helpful, and constructive. We're all here to learn.