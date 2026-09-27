# Review Dimensions — AI 评审维度详细标准

> 本文档定义每个评审维度的判断标准，确保不同 AI 模型执行评审时结果一致。
> 每个维度输出：`pass`（无问题）/ `warn`（有疑点，标注即可）/ `fail`（建议删除或需用户决定）。

---

## 1. 可信度（Credibility）— 必做

**目的**：识别内容在当前时间点是否仍然正确。

**判断标准**：

| 等级 | 条件 |
|------|------|
| pass | 内容为通用原理、方法论、不依赖特定版本的知识 |
| warn | 内容提到具体版本、API、工具版本，需要验证是否过时 |
| fail | 内容已被证实错误（如 API 已废弃、工具已停止维护、安全漏洞） |

**输出字段**：
```yaml
credibility:
  status: pass | warn | fail
  note: 简要说明（warn/fail 时必填）
  evidence: 证据链（≤30字，如 "Python 3.11 changelog: asyncio.run 行为变更"）
```

**示例**：
- pass："闭包是函数和其周围状态的引用"（通用原理）
- warn："`asyncio.run()` 在 Python 3.7 引入"（版本相关，需验证）
- fail："`urllib.parse.quote` 默认编码空格为 `+`"（Python 3 已变更行为）

---

## 2. 噪声（Noise）— 必做

**目的**：识别并去除口癖、情绪表达、无意义重复。

**判断标准**：

| 类型 | 示例 | 处理方式 |
|------|------|----------|
| 口癖 | "然后我发现…嗯…然后我试了一下…" | 去除 |
| 情绪表达 | "我当时快疯了" "这个坑太恶心了" | 去除（保留"这是一个常见坑"的事实） |
| 无意义重复 | "我试了第一种方法不行，又试了第二种方法也不行，最后第三种终于行了" → 精简为"前两种方法失败，第三种可行" | 精简 |
| 自我指涉 | "我的笔记里之前写过" "我之前踩过这个坑" | 去除（知识库是独立的，不需要自指） |
| 闲聊 | "今天天气不错" "午饭吃了啥" | 标记为 fail，建议不收录 |

**输出字段**：
```yaml
noise:
  status: pass | warn | fail
  detected_types: [口癖, 情绪表达, 无意义重复]  # warn 时列出检测到的类型
  cleaned_content: 清洗后的内容（如果发生了修改）
```

**规则**：
- 检测到噪声时，AI 直接重写清洗，不保留噪声原文
- 如果整张卡片全是噪声 → fail，不收录
- 如果部分内容有噪声 → warn，输出清洗后的版本

---

## 3. 冗余度（Redundancy）— 必做

**目的**：识别与已有知识库中内容的重复。

**判断标准**：

- 执行 embedding 检索，top-k=5
- LLM 对比检索结果与当前卡片内容
- 相似度 > 80% → 判断为重复

| 等级 | 条件 | 处理 |
|------|------|------|
| pass | 无重复内容 | 正常入库 |
| warn | 部分重复（50%-80% 相似），但有新增信息 | 建议合并到已有卡片，或标记为补充 |
| fail | 完全重复（>80% 相似），无新增信息 | 建议删除，或在已有卡片中补充来源 |

**输出字段**：
```yaml
redundancy:
  status: pass | warn | fail
  similar_cards:
    - path: 编程/异步.md
      similarity: 0.85
      overlap: "都描述了 asyncio.run() 的基本用法"
  suggestion: merge | supplement | reject
```

---

## 4. 迁移建议（Placement）— 必做

**目的**：判断这张卡片在知识库中应该放在哪里。

**判断标准**：

- LLM 根据卡片内容推断 `domain` 和 `subtopic`
- 检索知识库现有结构，判断：
  - 已有匹配文件 → 建议并入
  - 无匹配但主题相近 → 建议新建在相邻位置
  - 主题过于宽泛 → 建议进一步拆分

**输出字段**：
```yaml
placement:
  suggested_path: 编程/异步.md
  strategy: merge | new | split | adjacent
  reasoning: 一句话说明（≤30字）
  confidence: high | medium | low
```

**处理**：
- `confidence: high` → 阶段 4 自动执行
- `confidence: medium` → 写入 review，列出候选路径
- `confidence: low` → 写入 review，请求用户决定

---

## 5. 时效性（Timeliness）— 有条件

**目的**：标注内容的时间背景。

**判断标准**：

| 等级 | 条件 |
|------|------|
| pass | 内容无时间敏感性（通用原理、方法论） |
| warn | 内容与特定时间点相关（如"2024 年以前的 API"） |
| fail | 内容已明确过时 |

**输出字段**：
```yaml
timeliness:
  status: pass | warn | fail
  time_context: 内容适用的时间范围（如 "Python 3.7-3.10"）
  note: 简要说明
```

**处理**：
- warn → 在卡片中添加时间背景标注，不阻止入库
- fail → 标记为 ⚠️ 或建议不收录

---

## 6. 完整度（Completeness）— 有条件

**目的**：识别内容是否残缺，是否需要补充上下文。

**判断标准**：

| 等级 | 条件 |
|------|------|
| pass | 内容自包含，可独立理解 |
| warn | 缺少关键上下文（如"配置了 proxy"但没写配置内容） |
| fail | 内容碎片化，无法独立成文 |

**输出字段**：
```yaml
completeness:
  status: pass | warn | fail
  missing_context: 缺失的内容描述（≤30字）
  suggestion: 是否需要补充 / 是否可独立成文
```

**处理**：
- warn → 在卡片中添加 ❓ 标记，注明缺失内容
- fail → 标记为不完整，写入 review

---

## 评审汇总规则

每张卡片的评审结果汇总为：

```yaml
review:
  overall: approved | review | rejected
  dimensions:
    credibility: pass
    noise: pass
    redundancy: pass
    placement: { path: xxx, confidence: high }
    timeliness: pass
    completeness: pass
  action: integrate | review | reject
  review_reason: 如果 action=review，说明原因（≤50字）
```

**决策逻辑**：
- 任一必做维度 = fail → `rejected`
- 必做维度全 pass + 有条件维度无 fail → `approved`
- 其他情况 → `review`（写入 review 文件）
