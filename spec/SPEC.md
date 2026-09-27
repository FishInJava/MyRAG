# MyRAG — 个人知识库系统 Spec

> 本文档是从设计对话（`plan1.md`）和管道规范（`spec/PIPELINE.md`）中提取的正式需求规格。
> 面向 AI 实现者和未来维护者。

---

## Problem Statement

个人知识分散在 Obsidian 笔记、PDF、网页、Session 对话等多个来源中，格式不统一、风格不统一、内容未经评审。用户需要一个本地知识库系统，将这些原始知识经 AI 评审后，整合成一本"给人看的书"——格式统一、风格统一、内容经可信度评估，以后只读这个新知识库，不再回看原始笔记。

## Solution

构建一个 5 阶段 AI 管道（提取 → 原子化 → 评审 → 整合 → 索引），将原始文件自动处理为 Obsidian 可读的结构化 markdown 文件。系统运行在 Windows 原生环境，以独立 git 仓库保存 AI 产物，通过 spec 文件定义输入输出和评审标准，确保任何 AI 模型都能接手执行。

## User Stories

1. As a knowledge worker, I want to drop a PDF into a `newData/` folder, so that AI automatically extracts and reorganizes its content into my knowledge base.
2. As a learner, I want my Obsidian notes to be processed alongside PDFs and web pages, so that all my knowledge sources contribute to a unified knowledge base.
3. As a user, I want AI to rewrite content in my personal writing style (HBZ style), so that the knowledge base feels like it was written by me.
4. As a reader, I want every output file to have a consistent frontmatter and structure, so that I can navigate the knowledge base easily in Obsidian.
5. As a reviewer, I want AI to flag outdated or low-confidence content with inline markers, so that I know which parts need human verification.
6. As a knowledge curator, I want AI to merge duplicate content across sources into a single location, so that the knowledge base doesn't have redundant entries.
7. As a minimalist, I want simple ideas and one-sentence insights to be integrated directly without heavy review, so that the pipeline doesn't over-engineer trivial content.
8. As a user, I want uncertain decisions to be written to a review file instead of blocking the pipeline, so that processing continues without my intervention.
9. As a knowledge builder, I want AI to suggest where new content should go in the existing knowledge base, so that I don't have to manually reorganize.
10. As a long-term user, I want the knowledge base to evolve into a "book" organized by domain and subtopic, so that I can learn and review systematically.
11. As a privacy-conscious user, I want to control which content gets sent to cloud LLMs, so that sensitive information stays local.
12. As a Windows user, I want the entire system to run natively without Docker, so that it integrates seamlessly with my Obsidian setup.
13. As a spec-driven developer, I want all AI processing rules to be documented in human-readable spec files, so that I can switch AI models without rewriting logic.
14. As a git user, I want all knowledge base changes to be auto-committed, so that I have version history and can roll back if needed.
15. As a future-proof user, I want Session transcripts to be supported in V2, so that my AI conversation history becomes part of my knowledge base.

## Implementation Decisions

### Architecture

- **独立 git 仓库**：AI 产物存储在独立仓库，与原始数据（Obsidian vault、newData）隔离
- **个人尺度设计**：优先简洁、可读、可维护，不为大规模扩展做过度工程
- **Windows 原生**：无 Docker，使用系统原生工具（Python script + bash 命令）
- **Spec 优先**：核心价值是一份清晰的交接 spec，实现是可替换的细节

### 知识组织

- **概念原子化（Zettelkasten）**：每个知识点一张卡片，一个子主题一个文件
- **文件夹 = 领域，文件 = 子主题，文件内 TOC = 章节**：像一本书的结构
- **整合优于链接**：AI 将分散在各处的同一主题知识聚拢到最合适位置，而不是建立 `[[wikilink]]` 跳转
- **跨书吸收**（V2）：新内容进来后，检查是否需要给已有卡片补充链接或更新内容

### 5 阶段管道

```
阶段 1 EXTRACT：不同来源统一为纯文本 + 结构化元数据
阶段 2 ATOMIZE：LLM 将文本拆成知识点卡片草稿
阶段 3 REVIEW：多维评审（可信度/噪声/冗余/归属），仅对存疑内容执行
阶段 4 INTEGRATE：卡片写入 myObsidian/，建立链接，更新 TOC
阶段 5 INDEX：维护 myObsidian/_meta/ 全局索引
```

### 输出契约（Output Contract）

- **位置**：`template/` 目录，4 个文件定义输出格式和风格
- **加载时机**：阶段 2 ATOMIZE 和阶段 4 INTEGRATE 前必须加载并注入 LLM prompt
- **内容**：
  - `0生成MD文档时注意事项.md`：frontmatter 规则、符号使用规范
  - `1笔记属性.md`：frontmatter 模板
  - `ME/HBZ风格prompt.md`：HBZ 写作风格定义（语气、结构、句式、用词）
  - `ME/个人风格提取Prompt.md`：风格分析的参考 prompt

### 评审策略

- **默认直接整合**：简单的想法、一句话洞察、明显正确的常识直接进入阶段 4
- **评审触发条件**：可信度存疑 / 与已有内容高度重复 / 归属不确定 / 需要清洗噪声
- **6 个评审维度**（详见 `spec/REVIEW_DIMENSIONS.md`）：
  - 必做：可信度、噪声、冗余度、迁移建议
  - 有条件：时效性、完整度
- **输出**：无问题直接入库，有问题进 `myObsidian/_meta/reviews/xxx.review.md`（精简证据链，每项 ≤ 3 行）

### 关联建立

- **embedding 检索驱动**：处理时对知识库执行 embedding 检索（top-k=5），LLM 判断是否建链接
- **只建一次**：链接在处理阶段建立，不运行时自动维护

### 增量策略

- **SHA256 去重**：检查 `newData/.processed` 记录，已处理的跳过
- **处理新增源 + 反向检查已有卡片**（V2）：新内容进来后，检查是否需要给已有卡片补充内容

### 不确定项处理

- **静默自动执行**：确定性操作不打扰用户
- **精简 review 文件**：AI 置信度不足时才写入 review，每个待决定项不超过 3 行（问题 + 建议 + 精简证据）
- **用户事后查看**：review 文件在 `myObsidian/_meta/reviews/` 中，用户用其他 Agent 详细了解

### 技术栈

| 层 | 工具 | 用途 |
|----|------|------|
| Embedding | `chromadb` | 向量存储 + 检索 |
| LLM 调用 | `litellm` | 统一接口，支持多模型 |
| PDF 提取 | `pdfplumber` | PDF 文本提取 |
| 格式转换 | `pandoc` | HTML/DOCX → Markdown |
| 管道编排 | 手写 Python script | 无额外依赖 |
| 版本控制 | git | 自动 commit |

### 触发方式

- **手动触发**：`/process [路径]`（项目级 slash command）
- 支持文件路径、目录路径、或不提供路径（默认处理 `newData/`）

### 数据结构

详见 `spec/schema.yaml`，包括：
- `InputMeta`：输入文件元数据
- `ExtractOutput`：提取输出
- `CardDraft`：卡片草稿（无长度限制）
- `ReviewResult`：评审结果（可选，简单内容跳过）
- `IntegrateOutput`：整合输出
- `VaultFrontmatter`：vault 文件 frontmatter
- `ReviewReport`：review 报告（可选）

## Testing Decisions

- **测试目标**：测试外部行为（输入文件 → 输出文件），不测试 LLM 逻辑（不可 mock）
- **测试模块**：
  - `extract.py`：不同格式文件的提取正确性
  - `atomize.py`：卡片拆分的完整性
  - `integrate.py`：文件写入、TOC 更新、链接建立
  - `pipeline.py`：端到端流程、去重机制、错误处理
- **测试方式**：
  - 单元测试：文件提取、hash 计算、路径推断
  - 集成测试：用小样本文件跑完整管道，验证输出文件结构和内容
  - 回归测试：git tag `初版讨论结束` 作为基准

## Out of Scope

- **V2 才做**：
  - Session transcript 解析
  - 跨书吸收整合（已有卡片的反向更新）
  - 策略建议中间层（AI 给出方案，用户选择执行）
  - OCR（PDF 无文本层时）
- **不做**：
  - Web 界面或 API 服务
  - 多用户支持
  - 大规模知识库优化（个人尺度，不追求规模）
  - Docker 化部署
  - 自动触发（文件系统监控 / 定时任务）

## Further Notes

- **设计理念**（7 条，详见 `README.md`）：
  1. 知识库是给人看的，不是给 AI 训练的
  2. 整合优于链接
  3. AI 评审，人不审批
  4. 从用户自己的输出开始
  5. 个人尺度，不追求规模
  6. Spec 优先，实现其次
  7. Windows 原生，无容器
- **完整设计对话**：`plan1.md`（26 个问答，每条决策都有用户选择的理由）
- **当前状态**：设计阶段已完成，代码骨架已提交，tag `初版讨论结束`
- **使用方式**：在 Obsidian 中用 Claudian 插件唤起 Claude，输入 `/process [路径]`
- **可扩展性**：评审维度、输出契约、技术栈都可以通过修改 spec 文件切换，不需要改代码
