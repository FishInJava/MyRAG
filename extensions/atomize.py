"""
MyRAG Atomize — 阶段 2: 将提取的文本原子化为知识点卡片草稿

使用 LLM 将文本拆成独立的知识点，每张卡片一个知识点。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .schemas import ExtractOutput, CardDraft, SourceRef
from .config import PROJECT_ROOT, TEMPLATES_DIR, LLM_MODEL, LLM_API_KEY


# ─── 输出契约加载 ──────────────────────────────────────────────────

def load_output_contract() -> dict[str, str]:
    """从 template/ 加载所有输出契约文件"""
    contract = {}
    if not TEMPLATES_DIR.exists():
        return contract
    for f in sorted(TEMPLATES_DIR.rglob("*.md")):
        contract[f.name] = f.read_text(encoding="utf-8")
    return contract


# ─── Prompt 构建 ───────────────────────────────────────────────────

def build_atomize_prompt(text: str, output_contract: dict[str, str]) -> str:
    """构建原子化 prompt，注入输出契约"""
    # 加载输出契约关键部分
    notes_rules = output_contract.get("0生成MD文档时注意事项.md", "")
    style_prompt = output_contract.get("ME/HBZ风格prompt.md", "")

    prompt = f"""你是一个知识管理专家，负责将文本内容原子化为独立的知识点卡片。

## 输出规范（必须遵守）

### 1. 文档生成规则
{notes_rules}

### 2. 写作风格
{style_prompt}

## 任务

将以下文本拆分成独立的知识点卡片。每张卡片应该：
- 聚焦一个明确的知识点
- 用 HBZ 风格重写（清晰、直接、有判断）
- 包含标题、内容、来源引用
- 长度不限，以"讲清楚"为边界

## 输入文本

{text}

## 输出格式

输出 YAML 格式的卡片列表：

```yaml
cards:
  - id: card_001
    title: 卡片标题
    domain: 领域（如：编程、踩坑、设计）
    subtopic: 子主题（如：异步、Docker）
    content: |
      AI 用自己的话重写的内容，遵循 HBZ 风格。
    source_refs:
      - file: 来源文件路径
        location: 原文位置描述
        quote: 关键原文片段（可选）
    tags:
      - 标签1
      - 标签2
```

只输出 YAML，不要有其他解释。"""
    return prompt


# ─── LLM 调用 ──────────────────────────────────────────────────────

def call_llm(prompt: str) -> str:
    """调用 LLM 生成响应"""
    try:
        import litellm
    except ImportError:
        raise ImportError("litellm not installed. Run: pip install litellm")

    # 从环境变量读取 API key
    api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("Missing API key. Set ANTHROPIC_API_KEY or OPENAI_API_KEY")

    response = litellm.completion(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        api_key=api_key,
        max_tokens=8192,
        temperature=0.3,
    )

    return response.choices[0].message.content


# ─── YAML 解析 ─────────────────────────────────────────────────────

def parse_cards_yaml(yaml_text: str) -> list[dict[str, Any]]:
    """解析 LLM 返回的 YAML 卡片列表"""
    import yaml

    # 提取 YAML 块（LLM 可能会加 ```yaml ... ``` 包裹）
    if "```yaml" in yaml_text:
        yaml_text = yaml_text.split("```yaml")[1].split("```")[0]
    elif "```" in yaml_text:
        yaml_text = yaml_text.split("```")[1].split("```")[0]

    try:
        data = yaml.safe_load(yaml_text)
        if isinstance(data, dict) and "cards" in data:
            return data["cards"]
        elif isinstance(data, list):
            return data
        else:
            return []
    except Exception as e:
        raise ValueError(f"Failed to parse YAML: {e}\nRaw output:\n{yaml_text}")


# ─── 主入口 ────────────────────────────────────────────────────────

def atomize(extract_output: ExtractOutput, output_contract: dict[str, str]) -> list[CardDraft]:
    """将提取的文本原子化为卡片草稿

    Args:
        extract_output: 阶段 1 的提取结果
        output_contract: 从 template/ 加载的输出契约

    Returns:
        卡片草稿列表
    """
    text = extract_output.text
    if not text.strip():
        return []

    # 构建 prompt（注入输出契约）
    prompt = build_atomize_prompt(text, output_contract)

    # 调用 LLM
    llm_response = call_llm(prompt)

    # 解析 YAML
    cards_data = parse_cards_yaml(llm_response)

    # 转换为 CardDraft 对象
    cards = []
    for i, card_data in enumerate(cards_data, 1):
        source_refs = []
        for ref in card_data.get("source_refs", []):
            source_refs.append(SourceRef(
                file=ref.get("file", ""),
                location=ref.get("location", ""),
                quote=ref.get("quote"),
            ))

        cards.append(CardDraft(
            id=card_data.get("id", f"card_{i:03d}"),
            title=card_data.get("title", f"未命名卡片 {i}"),
            domain=card_data.get("domain", "未分类"),
            subtopic=card_data.get("subtopic", "未分类"),
            content=card_data.get("content", ""),
            source_refs=source_refs,
            tags=card_data.get("tags", []),
        ))

    return cards
