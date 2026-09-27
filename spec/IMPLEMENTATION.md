# Implementation Reference — 技术实现参考

> 本文档记录 V1 的技术选型和实现细节。
> 实现随时可替换，只要输入输出符合 `schema.yaml` 和 `PIPELINE.md` 的定义。

---

## 技术栈

| 层 | 工具 | 用途 |
|----|------|------|
| Embedding | `chromadb` | 向量存储 + 检索 |
| LLM 调用 | `litellm` | 统一接口，支持多模型 |
| PDF 提取 | `pdfplumber` | PDF 文本提取 |
| 格式转换 | `pandoc` | HTML/DOCX → Markdown |
| 管道编排 | 手写 Python script | 无额外依赖 |
| 版本控制 | git | 自动 commit |
| Session 解析 | 手动导出 JSON | V2 |

## 安装

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install chromadb litellm pdfplumber pypandoc python-dotenv pyyaml
```

## 环境变量

```env
ANTHROPIC_API_KEY=xxx
OPENAI_API_KEY=xxx       # 可选，用于 embedding
CHROMA_DB_PATH=chroma/
```

## 核心脚本结构

```
extensions/
├── pipeline.py           # 主入口，5 阶段编排
├── extract.py            # 阶段 1: 提取
├── atomize.py            # 阶段 2: 原子化
├── review.py             # 阶段 3: 评审
├── integrate.py          # 阶段 4: 整合
├── index.py              # 阶段 5: 索引
├── schemas.py            # schema 定义 + 校验
└── config.py             # 配置加载
```

## 运行

```bash
# 处理 newData/ 中所有新增文件
python extensions/pipeline.py

# 处理指定文件
python extensions/pipeline.py newData/xxx.pdf
```

## 实现优先级

V1 最小可用：
1. `extract.py` — 基础提取（PDF、MD、TXT）
2. `pipeline.py` — 编排框架（阶段调用顺序）
3. `atomize.py` — 基础原子化（单卡片输出）
4. `review.py` — 基础评审（可信度 + 噪声）
5. `integrate.py` — 基础整合（新建文件 + frontmatter）

V2 增量：
- `review.py` — 冗余度检索（chromadb 集成）
- `integrate.py` — 嵌入已有卡片、跨书吸收
- Session transcript 解析
