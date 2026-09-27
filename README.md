# MyRAG — 个人知识库系统

## 项目定位

这不是一个通用的 RAG 系统。这是一个**个人阅读工具**：把分散在各处的知识（Obsidian 笔记、PDF、网页、Session 对话）经过 AI 评审后，整合成一本"给人看的书"。

核心理念：

1. **知识库是给人看的，不是给 AI 训练的**。输出格式统一、风格统一、内容经评审，人以后只读这个库。
2. **整合优于链接**。AI 的价值在于把分散在同一主题的知识聚拢到最合适的位置，而不是建立一堆 `[[wikilink]]` 让人跳来跳去。
3. **AI 评审，人不审批**。确定性操作静默自动执行，只在 AI 置信度不足时才产生 review 文件通知用户。
4. **从用户自己的输出开始**。原始材料是用户学习后的产物，AI 处理的是"已过滤的人类认知"。
5. **个人尺度，不追求规模**。优先简洁、可读、可维护。
6. **Spec 优先，实现其次**。核心价值是一份清晰的交接 spec，定义输入输出、评审维度、决策标准。
7. **Windows 原生，无容器**。跑在 Obsidian 同一台机器上，用系统原生工具。

## 系统架构

```
原始数据（只读）
  ├── Obsidian vault（已有笔记）
  ├── newData/（新放入的文件：PDF、HTML、DOCX、TXT）
  └── sessions/（导出的 Session transcript）

MyRAG 仓库
  ├── spec/           ← AI 交接标准（权威源）
  ├── extensions/            ← 管道实现（Python script）
  ├── newData/          ← 待处理文件（手动放入）
  └── myObsidian/          ← 最终知识库（Obsidian 打开这个目录）
      ├── 领域1/
      │   ├── 子主题1.md    ← "一本书"的一章
      │   └── 子主题2.md
      ├── 领域2/
      └── _meta/            ← 系统文件（TOC、索引等）
```

## 使用方式

1. 把待处理的文件放入 `newData/`
2. 运行管道：`python extensions/pipeline.py`
3. 管道输出到 `myObsidian/`
4. 如有不确定项，查看 `myObsidian/_meta/reviews/` 中的 `.review.md` 文件
5. 用 Obsidian 打开 `myObsidian/` 阅读

## V1 范围

- 输入：PDF / HTML / DOCX / TXT / Markdown / Obsidian 笔记
- 输出：Obsidian vault 中的结构化 markdown 文件
- AI 评审：可信度、噪声检测、冗余度、迁移建议
- 链接：embedding 检索 + LLM 判断，新建卡片时自动建立
- 不确定项：输出到 `.review.md`，不阻塞流程

V2 待实现：
- Session transcript 解析
- 跨书吸收整合（已有卡片的反向更新）
- 策略建议中间层（AI 给出方案，用户选择执行）
