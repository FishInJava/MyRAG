---
name: process
description: "处理 newData/ 中的文件，经 AI 评审后输出到 myObsidian/ 知识库。用法：/process [文件或目录路径]"
---

你正在执行 MyRAG 知识库管道的入口指令。

## 你的任务

1. 读取 `spec/PIPELINE.md` 获取完整管道规范
2. 从 `template/` 加载输出契约（frontmatter 格式、HBZ 风格、符号规范）
3. 执行 5 阶段管道：
   - 阶段 1 EXTRACT：提取文本 + 元数据
   - 阶段 2 ATOMIZE：原子化为知识点卡片（注入输出契约）
   - 阶段 3 REVIEW：评审（仅对存疑内容）
   - 阶段 4 INTEGRATE：整合到 myObsidian/（注入输出契约）
   - 阶段 5 INDEX：更新目录索引
4. 每阶段完成后打印简短摘要

## 输入路径

用户会在指令后提供路径（可能是绝对路径或相对路径）：
- 如果是文件 → 只处理该文件
- 如果是目录 → 处理目录下所有新增文件
- 如果未提供 → 处理 `newData/` 下所有新增文件

去重机制：检查 `newData/.processed` 中的 SHA256 记录，已处理过的跳过。

## 关键约束

- 输出契约（`template/`）必须在阶段 2 和阶段 4 前加载并注入到 LLM prompt
- 简单的想法、一句话洞察直接整合，不要过度评审
- 不确定项写入 `myObsidian/_meta/reviews/`，不阻塞流程
- 完成后自动 git commit

## 执行

现在开始执行。先读取 spec 和 template，然后处理用户指定的路径。
