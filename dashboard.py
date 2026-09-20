"""
Twitter Bot Dashboard (Streamlit)
═══════════════════════════════════════════════════════════════
启动:
  streamlit run dashboard.py --server.port 8501

页面:
  - 📊 总览: 今日 / 本周 互动量
  - 👥 用户: Top 互动用户
  - 💬 评论: AI 生成的评论样例
  - 🎯 表现: hashtag 效果排行
  - ⚙️ 控制: Bot 状态 + 启停
"""

import streamlit as st
import pandas as pd
import time
from pathlib import Path

import analyzer
import ab_test


# ── 页面配置 ──
st.set_page_config(
    page_title="Twitter Bot Dashboard",
    page_icon="🐦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 侧边栏 ──
st.sidebar.title("🐦 Twitter Bot")
st.sidebar.markdown("---")

# Bot 状态
pid_file = Path("bot.pid")
log_file = Path("bot.log")

if pid_file.exists():
    pid = pid_file.read_text().strip()
    st.sidebar.success(f"✅ Bot 运行中\n\nPID: `{pid}`")
else:
    st.sidebar.warning("⏹️ Bot 未运行")

st.sidebar.markdown("### 操作")

col1, col2 = st.sidebar.columns(2)
with col1:
    if st.button("▶️ 启动 (DRY)"):
        st.info("请在终端运行: `./start.sh`")
with col2:
    if st.button("🛑 停止"):
        st.info("请在终端运行: `./start.sh stop`")

st.sidebar.markdown("### 其他")
if st.sidebar.button("🔄 刷新数据"):
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.caption(f"🕐 {time.strftime('%Y-%m-%d %H:%M:%S')}")
st.sidebar.caption("Streamlit Dashboard for Twitter Bot v3")


# ── 主区 ──
st.title("🐦 Twitter Bot Dashboard")

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 总览", "👥 用户", "💬 评论", "🎯 表现", "🧪 A/B 测试", "📜 日志"
])


# ── Tab 1: 总览 ──
with tab1:
    st.header("📊 今日 / 本周 互动量")

    stats = analyzer.get_today_stats()
    weekly = analyzer.get_weekly_trend()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("今日评论", stats["comments"])
    col2.metric("今日点赞", stats["likes"])
    col3.metric("今日关注", stats["follows"])
    col4.metric("今日触达", stats["reach"])

    col1, col2, col3 = st.columns(3)
    col1.metric("扫到推文", stats["scanned"])
    col2.metric("平均质量分", f"{stats['avg_score']:.2f}")
    col3.metric("今日发帖", stats.get("posts", 0))

    st.markdown("---")
    st.subheader("📈 最近 7 天")

    if weekly:
        df = pd.DataFrame(weekly)
        df["total"] = df["comments"] + df["likes"] + df["follows"]
        st.bar_chart(df.set_index("date")[["comments", "likes", "follows"]])
        st.line_chart(df.set_index("date")[["reach"]])

        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("还没有数据, 跑跑 bot 再看 👀")


# ── Tab 2: 用户 ──
with tab2:
    st.header("👥 Top 互动用户")

    top_users = analyzer.get_top_users(limit=30)
    if top_users:
        df = pd.DataFrame(top_users)
        st.bar_chart(df.set_index("user_id")[["total"]])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("还没有互动用户")


# ── Tab 3: 评论 ──
with tab3:
    st.header("💬 AI 生成的最近评论")

    replies = analyzer.get_recent_replies(limit=50)
    if replies:
        for r in replies[:20]:
            with st.expander(f"**@{r['name'] or r['user_id']}** · {r['time']}"):
                st.markdown(f"**原推**: {r['original']}")
                st.markdown(f"**AI 回复**: {r['reply']}")
        st.caption(f"共 {len(replies)} 条")
    else:
        st.info("还没有 AI 评论记录")


# ── Tab 4: Hashtag 表现 ──
with tab4:
    st.header("🎯 Hashtag 效果")

    perf = analyzer.get_hashtag_performance()
    if perf:
        df = pd.DataFrame(perf)
        st.bar_chart(df.set_index("hashtag")[["count"]])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("还没有 hashtag 数据")


# ── Tab 5: A/B Test ──
with tab5:
    st.header("🧪 A/B Test - Prompt 效果对比")

    try:
        ab_test.extend_ab_db()
        perf = ab_test.get_performance()

        if perf and any(p["users"] > 0 for p in perf):
            df = pd.DataFrame(perf)
            df["reply_rate"] = (df["reply_rate"] * 100).round(1).astype(str) + "%"

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("变体数", len(perf))
            col2.metric("总用户", df["users"].sum())
            col3.metric("总发送", df["comments_sent"].sum())
            col4.metric("总回复", df["replied"].sum())

            st.markdown("---")

            # 图表
            chart_df = pd.DataFrame(perf).set_index("variant")[["reply_rate"]]
            st.bar_chart(chart_df)

            # 详情表
            st.subheader("详细数据")
            st.dataframe(
                df[["variant", "users", "comments_sent", "replied", "reply_rate", "liked_back", "followed_back"]],
                use_container_width=True, hide_index=True,
            )

            # ⭐ 最佳
            best = perf[0]
            if best["reply_rate"] > 0:
                st.success(f"⭐ 当前最佳: **{best['variant']}** (回复率 {best['reply_rate']*100:.1f}%)")
                st.info("💡 调低其他 variant 的 weight, 提高这个的 weight")

            # 变体 prompt 详情
            st.markdown("---")
            st.subheader("📝 Prompt 内容")
            for name in ab_test.PROMPT_VARIANTS:
                with st.expander(f"{name}"):
                    st.code(ab_test.PROMPT_VARIANTS[name]["text"], language="text")
                    st.caption(f"weight = {ab_test.PROMPT_VARIANTS[name]['weight']}")
        else:
            st.info("还没有 A/B 测试数据, bot 跑一阵子就有了")
    except Exception as e:
        st.error(f"A/B 测试模块未加载: {e}")


# ── Tab 6: 日志 ──
with tab6:
    st.header("📜 实时日志")

    if log_file.exists():
        lines = log_file.read_text(encoding="utf-8", errors="ignore").splitlines()
        recent = "\n".join(lines[-200:])
        st.code(recent, language="log")

        if st.button("🔄 刷新日志"):
            st.rerun()
    else:
        st.info("还没有日志, 跑跑 bot 再看 👀")


st.markdown("---")
st.caption("Twitter Bot v3 · 数据每 30 秒自动刷新 · 详见 analyzer.py")