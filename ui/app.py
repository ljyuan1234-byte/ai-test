"""
Streamlit 可视化界面

启动：streamlit run ui/app.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# 确保项目根目录在 sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from skills import get_registry
from skills.pipeline import SkillPipeline

# ─── 页面配置 ─────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="汽车资讯 AI 助手",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── 样式 ─────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    .main-header { font-size: 2rem; color: #1a73e8; font-weight: 700; }
    .skill-badge {
        display: inline-block; background: #e8f0fe; color: #1a73e8;
        border-radius: 12px; padding: 2px 10px; margin: 2px; font-size: 0.8rem;
    }
    .result-card {
        border: 1px solid #dadce0; border-radius: 8px; padding: 16px; margin: 8px 0;
        background: #fff;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ─── 异步辅助 ─────────────────────────────────────────────────────────────────
def run_async(coro):
    """在 Streamlit 中安全运行异步代码"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


# ─── 侧边栏：系统状态 ─────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🔧 系统状态")
    registry = get_registry()
    skills_info = registry.list_skills()
    if skills_info:
        for s in skills_info:
            st.markdown(
                f'<span class="skill-badge">✓ {s["name"]}</span>',
                unsafe_allow_html=True,
            )
    else:
        st.warning("暂无已注册 Skill")

    st.divider()
    st.markdown("## ⚙️ 抓取设置")
    sources = st.multiselect(
        "数据源",
        options=["autohome", "dongchedi"],
        default=["autohome", "dongchedi"],
        format_func=lambda x: {"autohome": "汽车之家", "dongchedi": "懂车帝"}.get(x, x),
    )
    max_items = st.slider("每源最多抓取条数", min_value=3, max_value=30, value=10)
    fetch_full = st.checkbox("抓取全文（较慢）", value=False)
    top_k = st.slider("RAG 检索条数", min_value=1, max_value=20, value=5)

    st.divider()
    st.caption("基于 Skills 架构 · ChromaDB · Streamlit")


# ─── 主页面 Tab 布局 ──────────────────────────────────────────────────────────
st.markdown('<div class="main-header">🚗 汽车资讯 AI 助手</div>', unsafe_allow_html=True)
st.caption("从汽车之家、懂车帝抓取最新资讯 → 向量化存储 → 智能检索问答")

tab_crawl, tab_query, tab_browse = st.tabs(["📡 抓取资讯", "🔍 智能问答", "📚 浏览知识库"])


# ─── Tab 1: 抓取资讯 ──────────────────────────────────────────────────────────
with tab_crawl:
    st.markdown("### 搜索最新车辆资讯并存入知识库")
    crawl_query = st.text_input(
        "搜索关键词",
        placeholder="例如：特斯拉Model Y 2025款、宝马X5新款、比亚迪汉",
        key="crawl_query",
    )
    if st.button("🚀 开始抓取并存储", type="primary", use_container_width=True):
        if not crawl_query.strip():
            st.warning("请输入搜索关键词")
        else:
            with st.spinner(f"正在从 {', '.join(sources)} 抓取：{crawl_query} ..."):
                async def _crawl():
                    reg = get_registry()
                    pipeline = SkillPipeline(
                        skills=[
                            reg.require("web_crawler"),
                            reg.require("formatter"),
                            reg.require("vector_store"),
                        ],
                        name="crawl_pipeline",
                    )
                    return await pipeline.run(
                        initial_data={
                            "query": crawl_query,
                            "sources": sources,
                            "max_items": max_items,
                            "fetch_full": fetch_full,
                            "vs_action": "store",
                        }
                    )

                ctx = run_async(_crawl())

            if ctx.has_errors:
                for e in ctx.errors:
                    st.error(e)
            else:
                articles = ctx.get("formatted_articles", [])
                stored = ctx.get("stored_ids", [])
                st.success(f"✅ 抓取 {len(articles)} 篇，已存入向量库 {len(stored)} 条")
                for art in articles:
                    with st.expander(f"📄 {art.get('title', '无标题')} — {art.get('source', '')}"):
                        st.markdown(art.get("formatted_text", ""), unsafe_allow_html=False)
                        if art.get("url"):
                            st.markdown(f"🔗 [原文链接]({art['url']})")


# ─── Tab 2: 智能问答 ──────────────────────────────────────────────────────────
with tab_query:
    st.markdown("### 向量检索 + LLM 智能问答（RAG）")
    st.info("💡 先在「抓取资讯」标签页存入数据，再在此处提问")
    rag_query = st.text_input(
        "你的问题",
        placeholder="例如：宝马X5和奔驰GLE哪个更值得买？",
        key="rag_query",
    )
    if st.button("🔍 开始问答", type="primary", use_container_width=True):
        if not rag_query.strip():
            st.warning("请输入问题")
        else:
            with st.spinner("正在检索知识库并生成回答..."):
                async def _rag():
                    reg = get_registry()
                    pipeline = SkillPipeline(
                        skills=[
                            reg.require("vector_store"),
                            reg.require("rag"),
                        ],
                        name="rag_pipeline",
                    )
                    return await pipeline.run(
                        initial_data={
                            "query": rag_query,
                            "vs_action": "search",
                            "top_k": top_k,
                        }
                    )

                ctx = run_async(_rag())

            if ctx.has_errors:
                for e in ctx.errors:
                    st.error(e)

            answer = ctx.get("rag_answer", "")
            sources_used = ctx.get("rag_sources", [])
            search_results = ctx.get("search_results", [])

            if answer:
                st.markdown("#### 🤖 AI 回答")
                st.markdown(answer)

            if search_results:
                st.divider()
                st.markdown(f"#### 📎 引用的 {len(search_results)} 条资讯")
                for i, r in enumerate(search_results, 1):
                    meta = r.get("metadata", {})
                    with st.expander(f"{i}. {meta.get('title', '(无标题)')} — {meta.get('source', '')}"):
                        st.write(r.get("text", ""))
                        if meta.get("url"):
                            st.markdown(f"🔗 [原文链接]({meta['url']})")
                        st.caption(f"相似度距离: {r.get('distance', 'N/A'):.4f}")


# ─── Tab 3: 浏览知识库 ────────────────────────────────────────────────────────
with tab_browse:
    st.markdown("### 浏览知识库统计")
    if st.button("🔄 刷新统计", use_container_width=True):
        try:
            import chromadb
            from chromadb.config import Settings
            client = chromadb.PersistentClient(
                path="./data/vector_db",
                settings=Settings(anonymized_telemetry=False),
            )
            collections = client.list_collections()
            if collections:
                for col in collections:
                    c = client.get_collection(col.name)
                    st.metric(label=f"集合：{col.name}", value=f"{c.count()} 条文档")
            else:
                st.info("知识库为空，请先抓取资讯")
        except Exception as exc:  # noqa: BLE001
            st.error(f"无法读取知识库: {exc}")

    st.divider()
    st.markdown("#### 已注册 Skills")
    for s in registry.list_skills():
        st.markdown(
            f"**{s['name']}** `v{s['version']}`  \n{s['description']}"
        )
