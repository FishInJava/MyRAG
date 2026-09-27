# Pipeline Spec — AI 交接标准

> 任何 AI 模型读取本文档后，应能独立执行完整的知识库构建管道。
> 本文档是权威源，`SKILL.md` 仅为快捷入口。

---

## 0. 输出契约（必读）

在执⾏任何阶段之前，必须先读取以下文件，它们定义了输出结果的**格式、风格和属性**。这些文件是本 spec 的一部分，缺省不可。

```
00模板/
├── 0生成MD文档时注意事项.md   ← 生成 MD 文档的强制规则
├── 1笔记属性.md              ← frontmatter 模板
├── ME/
│   ├── HBZ风格prompt.md       ← 写作风格定义（语气、结构、句式、用词）
│   └── 个人风格提取Prompt.md  ← 风格分析的参考 prompt
```

**读取时机**：
- **阶段 2 ATOMIZE**：生成卡片草稿前，读取 `0生成MD文档时注意事项.md` + `ME/HBZ风格prompt.md`，作为 LLM prompt 的一部分
- **阶段 4 INTEGRATE**：写入 `myObsidian/` 文件前，读取全部 4 个模板文件，确保输出格式和风格正确

**输出契约的核心约束**（摘要，完整内容以模板文件为准）：
1. 每张卡片开头必须有 frontmatter（参考 `1笔记属性.md`）
2. 允许使用符号 `🔥❗❓❌💡✏️🔍📝`，禁止使用人物表情
3. 文风严格遵循 `ME/HBZ风格prompt.md` 中定义的 HBZ 风格
4. 风格参考见 `ME/HBZ风格prompt.md`

---

## 1. 输入规范

### 1.1 支持的源类型

| 类型 | 扩展名 | 提取方式 | 特殊处理 |
|------|--------|----------|----------|
| PDF | `.pdf` | `pdfplumber` 提取文本 + 结构 | 保留章节标题层级 |
| HTML | `.html` `.htm` | `pandoc` 转 markdown | 去除导航/广告/脚本 |
| DOCX | `.docx` | `pandoc` 转 markdown | 保留标题层级 |
| Markdown | `.md` | 直接读取 | 保留 frontmatter |
| 纯文本 | `.txt` | 直接读取 | 无特殊处理 |
| Obsidian 笔记 | `.md`（来自 vault） | 直接读取 | 保留 `[[wikilink]]` 和 `#tag` |

### 1.2 输入目录

- **`newData/`**：用户手动放入的待处理文件
- **`sources/obsidian/`**：对 Obsidian vault 的只读引用（符号链接或复制）
- **`sources/sessions/`**：导出的 Session transcript（V2 支持）

### 1.3 输入去重

处理前检查 `newData/.processed/` 记录。对每个文件计算 SHA256：
- 已存在 → 跳过
- 新增 → 加入处理队列

---

## 2. 处理管道

管道为 5 阶段线性流程，每阶段有明确的输入输出。

```
[输入文件]
    ↓
阶段 1: EXTRACT（提取）
    ↓
阶段 2: ATOMIZE（原子化）
    ↓
阶段 3: REVIEW（评审）
    ↓
阶段 4: INTEGRATE（整合）
    ↓
阶段 5: INDEX（索引）
    ↓
[myObsidian/ 更新完成]
```

### 阶段 1: EXTRACT（提取）

**目的**：把不同格式的源文件统一为纯文本 + 结构化元数据。

**输入**：`newData/` 中的文件

**输出**：
```
intermediate/extract/{file_hash}/
├── text.txt          ← 纯文本内容
├── meta.yaml         ← 来源元数据
└── structure.json    ← 章节/段落结构（如有）
```

`meta.yaml` 结构：
```yaml
source_path: newData/xxx.pdf
source_type: pdf
file_hash: sha256:abc123
extracted_at: 2024-09-27T10:00:00Z
title: 从元数据或文件名推断
author: 可选
date: 可选（从元数据或文件日期推断）
```

**规则**：
- 去除页眉页脚、广告、导航栏等无关内容
- PDF 优先提取文本层，无文本层时才考虑 OCR（V2）
- 保留章节标题层级，存入 `structure.json`

### 阶段 2: ATOMIZE（原子化）

**目的**：把提取的文本拆成独立的知识点卡片草稿。

**输入**：`intermediate/extract/{hash}/text.txt` + `structure.json`

**输出**：
```
intermediate/atomize/{file_hash}/
├── cards.yaml        ← 卡片草稿列表
└── source_map.json   ← 原文位置 → 卡片映射
```

**LLM 任务**：
对输入文本执行原子化拆分，每张卡片草稿包含：

> **前置条件**：先读取 `00模板/0生成MD文档时注意事项.md` 和 `00模板/ME/HBZ风格prompt.md`，确保输出的内容符合 HBZ 风格和文档规范。

```yaml
cards:
  - id: card_001
    title: 候选标题
    domain: 候选领域（如：编程、踩坑、设计）
    subtopic: 候选子主题（如：异步、Docker）
    content: |
      AI 用自己的话重写的内容，长度不限。
      风格：遵循 HBZ 风格（见 00模板/ME/HBZ风格prompt.md）。
    source_refs:
      - file: 来源文件路径
        location: 原文位置描述
        quote: 关键原文片段（可选）
    tags:
      - python
      - asyncio
```

**原子化规则**：
- 一张卡片 = 一个知识点
- 同一主题的多个要点应拆成多张卡片，不要合并
- 过于宽泛的标题（如"Python 笔记"）需要进一步拆分
- 保留原文引用位置，方便溯源

### 阶段 3: REVIEW（评审）

**目的**：对每张卡片草稿执行多维评审，分类处理。

**评审触发条件**：
- 简单的想法、一句话洞察、明显正确的常识 → **直接进入阶段 4，跳过评审**
- 只有存在以下情况时才需要评审：
  - 内容可信度存疑（可能过时、与已知冲突）
  - 与已有知识库内容高度重复
  - 归属不确定（应该放在哪个领域/子主题）
  - 内容需要清洗（口癖、情绪、冗余）

**输入**：`intermediate/atomize/{hash}/cards.yaml`

**输出**（仅在触发评审时生成）：
```
intermediate/review/{file_hash}/
├── cards_approved.yaml    ← 通过评审的卡片
├── cards_review.md        ← 待用户决定的精简报告（可选）
└── review_meta.yaml       ← 本次评审统计（可选）
```

**评审维度**（每个维度判断 pass / warn / fail）：

| 维度 | 必做 | 判断标准 |
|------|------|----------|
| 可信度（credibility） | ✅ | 内容是否仍然正确？是否有过时信息？ |
| 噪声（noise） | ✅ | 是否包含口癖、情绪、无意义重复？ |
| 冗余度（redundancy） | ✅ | 是否与已有知识库中的内容重复？ |
| 迁移建议（placement） | ✅ | 应该放入知识库的哪个位置？ |

| 维度 | 有条件 | 判断标准 |
|------|--------|----------|
| 时效性（timeliness） | ⚠️ 标注 | 是否需要标注时间背景？ |
| 完整度（completeness） | ⚠️ 标注 | 内容是否残缺，是否需要补充上下文？ |

**评审结果分类**：

- **✅ approved**：直接进入阶段 4 整合
- **⚠️ review**：写入 `cards_review.md`，等待用户事后决定
- **🗑️ rejected**：记录原因，不进入知识库

**默认行为**：大多数卡片应该直接 approved 进入阶段 4。只有 AI 置信度不足时才标记为 review。不要过度评审——一个简单的想法、一句话洞察，找到它在知识库中的位置，直接加进去即可。

**review 文件格式**（`cards_review.md`，仅在生成 review 时创建）：

```markdown
# Review: {source_file} — {date}

## 摘要
- 处理卡片: N 张
- 直接入库: N 张
- 待你决定: N 张
- 建议删除: N 张

---

## 待决定项

### 1. {简短问题描述}
**来源**: `{源文件名}` → "{原文中的相关内容}"
**问题**: {一句话描述问题}
**建议**: {AI 建议的处理方式}
**证据**: {精简证据，≤50 字}

### 2. ...
```

**规则**：
- 每个待决定项不超过 3 行（问题 + 建议 + 证据）
- 只输出 AI 置信度不足的项目，不输出确定性决策
- 不阻塞管道流程，review 文件事后通知

### 阶段 4: INTEGRATE（整合）

**目的**：把通过评审的卡片写入知识库 myObsidian，建立与其他卡片的链接。

**输入**：`intermediate/review/{hash}/cards_approved.yaml`

**输出**：`myObsidian/` 中的 markdown 文件被创建或更新

**整合流程**（对每张卡片）：

```
1. 确定目标位置
   ├── LLM 根据 card.domain + card.subtopic 推断目标路径
   └── 路径格式: myObsidian/{domain}/{subtopic}.md

2. 检索已有内容
   ├── 对知识库执行 embedding 检索（top-k=5）
   └── 输入: card.content，检索与已有卡片的语义相似度

3. LLM 判断整合策略
   ├── 选项: 新建文件 / 并入现有文件 / 补充到现有文件
   └── 判断依据: 检索结果 + 卡片内容 + 已有文件结构

4. 执行写入
   ├── 新建: 创建 myObsidian/{domain}/{subtopic}.md，写入卡片内容
   ├── 合并: 把内容整合到目标文件的合适位置
   └── 更新: 在目标文件中添加内容，更新 TOC

5. 建立链接
   ├── 对检索到的相关卡片，在正文中添加 [[domain/subtopic|标题]] 链接
   └── 同时在相关卡片的合适位置添加回链（如果空间允许）
```

**myObsidian 文件结构**：

```markdown
---
domain: 编程
subtopic: 异步
created: 2024-09-27
updated: 2024-09-27
sources:
  - newData/python-async-notes.md
  - sources/obsidian/async-learning.md
confidence: high
---

# 异步编程

## 目录
- [事件循环基础](#事件循环基础)
- [asyncio 核心 API](#asyncio-核心-api)
- [常见陷阱](#常见陷阱)

## 事件循环基础

{AI 重写的内容，清晰、简洁、无口癖}

### 常见陷阱

⚠️ **注意**：Python 3.11 后 `asyncio.run()` 行为有变更，参见 [官方 changelog](链接)。

## 相关主题

- [[踩坑/Docker]] — 容器内事件循环的特殊配置
- [[编程/并发/线程]] — 线程与协程的选择
```

**规则**：
- 目标路径由 `domain/subtopic` 决定，LLM 在第一阶段推断
- 同名文件时：判断是合并还是新建带后缀的文件（如 `异步-2.md`）
- 链接只建一次（处理时），不运行时自动维护
- 文件内 TOC 随内容更新自动维护

> **前置条件**：写入文件前，先读取全部 `00模板/` 文件，确保：
> - frontmatter 格式正确（参考 `00模板/1笔记属性.md`）
> - 文风符合 HBZ 风格（参考 `00模板/ME/HBZ风格prompt.md`）
> - 符号使用规范（参考 `00模板/0生成MD文档时注意事项.md`）

### 阶段 5: INDEX（索引）

**目的**：维护知识库的可导航性。

**输出**：
```
myObsidian/_meta/
├── README.md          ← 全局导航（所有领域列表）
├── toc.yaml           ← 全局目录结构
└── reviews/           ← review 文件输出目录
    └── {date}-{source}.review.md
```

**每阶段输出后自动更新**：
- `myObsidian/_meta/toc.yaml`：记录所有 `domain/subtopic` 文件树
- `myObsidian/{domain}/README.md`：每个领域文件夹的索引（可选，按需生成）

---

## 3. 输出格式规范

> 输出的格式、风格、frontmatter 由 `00模板/` 中的文件定义（见第 0 节）。
> 以下仅为 schema 层面的字段说明，具体写作风格以模板文件为准。

### 3.1 frontmatter 字段

```yaml
---
domain: 领域名（如：编程、踩坑、设计）
subtopic: 子主题名（如：异步、Docker）
created: ISO 日期
updated: ISO 日期
sources:          ← 来源文件列表
  - newData/xxx.pdf
  - sources/obsidian/yyy.md
confidence: high | medium | low    ← AI 评审可信度
reviewed: true | false             ← 是否经过用户复查
tags:                               ← 检索标签
  - python
  - asyncio
---
```

### 3.2 可信度内联标注

在正文中对关键疑点使用内联标记：

| 标记 | 含义 | 使用场景 |
|------|------|----------|
| `⚠️` | 注意/存疑 | 内容可能过时、与某处冲突、需要复查 |
| `✅` | 已确认 | 内容经过多源验证，可信度高 |
| `❓` | 待补充 | 内容不完整，需要更多信息 |
| `🔄` | 已整合 | 此内容是从其他位置整合而来 |

---

## 4. 运行规范

### 4.1 触发方式

用户手动指定输入路径，AI 执行完整管道：

```
@newData/ 处理新放入的文件
@newData/xxx.pdf 只处理这个文件
```

### 4.2 执行要求

- 按阶段顺序执行，每阶段输出到 `intermediate/` 对应目录
- 每阶段完成后打印简短摘要
- 最终输出处理报告 + review 文件路径（如有）
- 自动 git commit（如果仓库已初始化）

### 4.3 错误处理

- 单个文件提取失败 → 跳过，记录到 `intermediate/errors/`，继续处理其他文件
- LLM 调用失败 → 重试 1 次，仍失败则标记该卡片为 `review` 状态
- myObsidian 写入冲突 → 生成带时间戳的备选文件名，写入 review 文件通知用户

---

## 5. 评审维度详细标准

详见 `spec/REVIEW_DIMENSIONS.md`

---

## 6. 技术实现参考

详见 `spec/IMPLEMENTATION.md`

> 实现细节随时可替换，只要输入输出符合本文档定义的 schema。
