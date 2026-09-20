FROM python:3.11-slim

# 系统依赖 (twikit + 一些常用库)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc curl \
    && rm -rf /var/lib/apt/lists/*

# 工作目录
WORKDIR /app

# 先装依赖, 利用 Docker 缓存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY bot.py memory.py analyzer.py dashboard.py multi_bot.py \
     telegram_bot.py image_gen.py notifier.py ab_test.py quality.py ./
COPY start.sh ./
RUN chmod +x start.sh

# 数据持久化目录
RUN mkdir -p /app/data /app/media /app/logs

# 数据放卷 (不被 image 固化)
VOLUME ["/app/data", "/app/media", "/app/logs"]

# 健康检查 (bot 进程在跑)
HEALTHCHECK --interval=60s --timeout=10s --retries=3 \
    CMD test -f /app/logs/bot.pid && ps -p $(cat /app/logs/bot.pid) > /dev/null || exit 1

# 默认启动 bot (DRY_RUN 模式)
CMD ["./start.sh", "dry"]