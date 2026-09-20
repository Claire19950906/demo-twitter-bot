#!/bin/bash
# ────────────────────────────────────────
# Twitter Bot 一键启动脚本
# ────────────────────────────────────────
# 用法:
#   ./start.sh          # 默认 DRY_RUN 启动
#   ./start.sh live     # LIVE 模式 (真发, 别随便用!)
#   ./start.sh stop     # 停止
#   ./start.sh status   # 看状态
# ────────────────────────────────────────

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

PID_FILE="bot.pid"
LOG_FILE="bot.log"

# 在 Docker 里, 把数据放 /app/{logs,data,media} 卷
# 本地运行时, 放当前目录
if [ -d "/app/logs" ]; then
    PID_FILE="/app/logs/bot.pid"
    LOG_FILE="/app/logs/bot.log"
fi

# ── 颜色 ──
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

start_bot() {
    local mode=$1

    # 检查已在跑
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            echo -e "${YELLOW}⚠️  Bot 已在运行 (PID=$pid)${NC}"
            echo "   停止: ./start.sh stop"
            exit 1
        else
            echo -e "${YELLOW}🧹 清理旧的 PID 文件${NC}"
            rm -f "$PID_FILE"
        fi
    fi

    # 检查 venv
    if [ ! -d "venv" ]; then
        echo -e "${YELLOW}📦 创建虚拟环境...${NC}"
        python3 -m venv venv
        source venv/bin/activate
        pip install -r requirements.txt
    else
        source venv/bin/activate
    fi

    # 检查 .env
    if [ ! -f ".env" ]; then
        echo -e "${RED}❌ 没有 .env 文件${NC}"
        echo "   cp .env.example .env 然后填账号密码"
        exit 1
    fi

    # 启动
    echo -e "${GREEN}🚀 启动 Twitter Bot ($mode 模式)${NC}"
    if [ "$mode" = "live" ]; then
        nohup python bot.py --live >> "$LOG_FILE" 2>&1 &
    else
        DRY_RUN=1 nohup python bot.py >> "$LOG_FILE" 2>&1 &
    fi
    local pid=$!
    echo $pid > "$PID_FILE"
    echo -e "${GREEN}✅ Bot 启动成功 (PID=$pid)${NC}"
    echo "   日志: tail -f $LOG_FILE"
    echo "   停止: ./start.sh stop"
    sleep 2
    echo ""
    tail -n 20 "$LOG_FILE" 2>/dev/null || echo "(日志暂无)"
}

stop_bot() {
    if [ ! -f "$PID_FILE" ]; then
        echo -e "${YELLOW}⚠️  没有 PID 文件, Bot 未运行?${NC}"
        exit 1
    fi

    local pid=$(cat "$PID_FILE")
    if ps -p "$pid" > /dev/null 2>&1; then
        echo -e "${YELLOW}🛑 停止 Bot (PID=$pid)...${NC}"
        kill -TERM "$pid" 2>/dev/null || true
        sleep 2
        if ps -p "$pid" > /dev/null 2>&1; then
            echo "   还在, 强杀"
            kill -9 "$pid" 2>/dev/null || true
        fi
        rm -f "$PID_FILE"
        echo -e "${GREEN}✅ Bot 已停止${NC}"
    else
        echo -e "${YELLOW}⚠️  PID $pid 已不存在, 清理 PID 文件${NC}"
        rm -f "$PID_FILE"
    fi
}

status_bot() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            echo -e "${GREEN}✅ Bot 正在运行 (PID=$pid)${NC}"
            echo "   运行时间: $(ps -o etime= -p $pid 2>/dev/null)"
            echo "   CPU%: $(ps -o %cpu= -p $pid 2>/dev/null)"
            echo "   内存: $(ps -o rss= -p $pid 2>/dev/null) KB"
        else
            echo -e "${YELLOW}⚠️  PID 文件存在但进程已死${NC}"
        fi
    else
        echo -e "${YELLOW}⏹️  Bot 未运行${NC}"
    fi
}

case "${1:-dry}" in
    dry|DRY)
        start_bot "DRY_RUN"
        ;;
    live|LIVE)
        echo -e "${RED}⚠️  LIVE 模式: bot 会真实发送 / 点赞 / 关注!${NC}"
        read -p "确认继续? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            start_bot "LIVE"
        else
            echo "已取消"
        fi
        ;;
    stop|STOP)
        stop_bot
        ;;
    status|STATUS)
        status_bot
        ;;
    logs|LOGS)
        tail -f "$LOG_FILE"
        ;;
    restart|RESTART)
        stop_bot
        sleep 1
        start_bot "${2:-dry}"
        ;;
    *)
        echo "用法: $0 {dry|live|stop|status|logs|restart}"
        echo "  dry     - DRY_RUN 启动 (默认, 安全)"
        echo "  live    - LIVE 启动 (真发, 需确认)"
        echo "  stop    - 停止"
        echo "  status  - 状态"
        echo "  logs    - 实时日志"
        echo "  restart - 重启"
        exit 1
        ;;
esac