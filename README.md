# 汽车资讯 AI 助手

基于 **Skills 架构** 的汽车资讯抓取、向量化存储与智能问答系统。

---

## 项目结构

```
analysis_search/
│
├── skills/                     ← ★ 核心：所有功能都是 Skill
│   ├── base.py                 ← BaseSkill 抽象基类 + SkillContext + SkillResult
│   ├── registry.py             ← SkillRegistry 全局注册中心（单例）
│   ├── pipeline.py             ← SkillPipeline 流水线编排
│   ├── __init__.py             ← 注册入口（新增 Skill 只改此文件）
│   │
│   ├── web_crawler/            ← Skill①：网页抓取
│   │   ├── skill.py
│   │   └── sites/
│   │       ├── autohome.py     ← 汽车之家爬虫
│   │       └── dongchedi.py    ← 懂车帝爬虫
│   │
│   ├── formatter/              ← Skill②：格式化输出
│   │   └── skill.py
│   │
│   ├── vector_store/           ← Skill③：ChromaDB 向量数据库
│   │   └── skill.py
│   │
│   └── rag/                    ← Skill④：检索增强生成
│       └── skill.py
│
├── mcp_server/
│   └── server.py               ← MCP Server（将 Skills 暴露为工具）
│
├── ui/
│   └── app.py                  ← Streamlit 可视化界面
│
├── data/
│   └── vector_db/              ← ChromaDB 持久化文件（自动创建）
│
├── config.yaml                 ← 所有可变参数
├── config.py                   ← 配置加载器
├── main.py                     ← 项目入口
└── requirements.txt
```

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置（可选）

编辑 `config.yaml` 或设置环境变量：
```bash
# 使用 OpenAI
set LLM_API_KEY=sk-xxxxx

# 使用本地 Ollama
# config.yaml 中将 llm.base_url 改为 "http://localhost:11434/v1"
# llm.model 改为 "qwen2:7b" 等
```
> 不配置 LLM 时，系统仍可正常抓取和检索，只是回答会直接返回原始检索片段。

### 3. 启动可视化界面

```bash
python main.py --mode ui
```

### 4. 命令行快速使用

```bash
# 抓取资讯并存入向量库
python main.py --mode crawl --query "特斯拉Model Y 2025款"

# RAG 智能问答
python main.py --mode ask --query "宝马X5和奔驰GLE哪个更值得买"

# 查看所有 Skill
python main.py --mode list
```

### 5. 启动 MCP Server

```bash
python main.py --mode mcp
```

---

## Skills 架构说明

### 核心设计原则

```
新增功能 = 新建一个 Skill 文件 + 在 skills/__init__.py 注册
          ↓ 不需要修改任何已有代码
```

### 关键组件

| 组件 | 职责 |
|---|---|
| `BaseSkill` | 所有 Skill 的抽象基类，定义 `execute()` 接口 |
| `SkillContext` | Pipeline 中 Skill 间共享的数据容器 |
| `SkillResult` | 统一的执行结果（成功/失败 + 数据） |
| `SkillRegistry` | 单例注册中心，管理所有 Skill |
| `SkillPipeline` | 将多个 Skill 串联，共享 SkillContext |

### 如何新增一个 Skill

假设你要新增「价格比较」Skill：

**第一步**：新建文件 `skills/price_compare/skill.py`

```python
from skills.base import BaseSkill, SkillContext, SkillResult

class PriceCompareSkill(BaseSkill):
    name = "price_compare"
    description = "比较多款车型的价格区间"
    version = "1.0.0"

    async def execute(self, context: SkillContext, **kwargs) -> SkillResult:
        articles = context.get("formatted_articles", [])
        # ... 你的逻辑 ...
        context.set("price_comparison", result)
        return SkillResult.ok(data=result, skill_name=self.name)
```

**第二步**：在 `skills/__init__.py` 的 `_register_all()` 中加一行

```python
from .price_compare.skill import PriceCompareSkill
registry.register(PriceCompareSkill())
```

**第三步**：在 Pipeline 中使用

```python
pipeline = SkillPipeline([
    registry.require("web_crawler"),
    registry.require("formatter"),
    registry.require("price_compare"),   # ← 新增
    registry.require("vector_store"),
])
```

就这三步，无需改动任何已有代码。

### 数据流向

```
用户输入 query
    ↓
context = SkillContext(data={"query": query})
    ↓
WebCrawlerSkill     → context["raw_articles"]
    ↓
FormatterSkill      → context["formatted_articles"]
                    → context["documents"]
    ↓
VectorStoreSkill    → 写入 ChromaDB
                    → context["stored_ids"]
    ↓
（查询时）
VectorStoreSkill    → context["search_results"]
    ↓
RAGSkill            → context["rag_answer"]
                    → context["rag_sources"]
```

---

## MCP 工具说明

| 工具名 | 功能 |
|---|---|
| `search_car_news` | 搜索资讯并存入向量库 |
| `query_knowledge` | RAG 智能问答 |
| `list_skills` | 查看所有已注册 Skill |

在 Claude Desktop 或其他 MCP 客户端的配置文件中添加：

```json
{
  "mcpServers": {
    "car-info": {
      "command": "python",
      "args": ["C:/path/to/analysis_search/main.py", "--mode", "mcp"]
    }
  }
}
```

---

## 扩展建议

- **新增数据源**：在 `skills/web_crawler/sites/` 下新建文件（如 `yiche.py` 易车），然后在 `WebCrawlerSkill` 的 `_SOURCE_MAP` 中注册
- **新增 Skill**：遵循上述三步流程
- **换向量模型**：修改 `config.yaml` 中的 `embedding_model`
- **换 LLM**：修改 `config.yaml` 中的 `llm` 配置，兼容任何 OpenAI 接口
