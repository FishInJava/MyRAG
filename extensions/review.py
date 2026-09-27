"""
MyRAG Review — 阶段 3: 对卡片草稿执行多维评审

评审维度：
- 必做：可信度、噪声、冗余度、迁移建议
- 有条件：时效性、完整度
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schemas import (
    CardDraft,
    ReviewResult,
    ReviewDimensions,
    DimensionResult,
    RedundancyResult,
    RedundancySimilarCard,
    PlacementResult,
    ReviewReport,
    ReviewSummary,
    ReviewItem,
)
from .config import PROJECT_ROOT, LLM_MODEL, LLM_API_KEY, SIMILARITY_THRESHOLD


# ─── Prompt 构建 ───────────────────────────────────────────────────

def build_review_prompt(card: CardDraft, existing_cards: list[str] = None) -> str:
    """构建评审 prompt"""
    existing_context = ""
    if existing_cards:
        existing_context = "\n\n## 已有知识库内容（部分）\n" + "\n".join(
            f"- {c[:200]}..." for c in existing_cards[:3]
        )

    prompt = f"""你是一个知识评审专家，负责评审一张知识点卡片的质量。

## 评审维度

1. **可信度（credibility）**：内容是否仍然正确？是否有过时信息？
2. **噪声（noise）**：是否包含口癖、情绪、无意义重复？
3. **冗余度（redundancy）**：是否与已有知识库内容重复（相似度 > 80%）？
4. **迁移建议（placement）**：应该放入知识库的哪个位置？
5. **时效性（timeliness）**：是否需要标注时间背景？
6. **完整度（completeness）**：内容是否残缺？

## 评审卡片

**标题**：{card.title}
**领域**：{card.domain}
**子主题**：{card.subtopic}
**内容**：
{card.content}

**来源**：
{chr(10).join(f"- {ref.file} ({ref.location})" for ref in card.source_refs)}{existing_context}

## 输出格式

输出 JSON：

```json
{{
  "credibility": {{
    "status": "pass|warn|fail",
    "note": "简要说明（warn/fail 时必填）",
    "evidence": "证据链（≤30字）"
  }},
  "noise": {{
    "status": "pass|warn|fail",
    "detected_types": ["口癖", "情绪表达"],
    "cleaned_content": "清洗后的内容（如果修改了）"
  }},
  "redundancy": {{
    "status": "pass|warn|fail",
    "similar_cards": [
      {{"path": "路径", "similarity": 0.85, "overlap": "重叠说明"}}
    ],
    "suggestion": "merge|supplement|reject"
  }},
  "placement": {{
    "suggested_path": "domain/subtopic.md",
    "strategy": "merge|new|split|adjacent",
    "reasoning": "一句话说明",
    "confidence": "high|medium|low"
  }},
  "timeliness": {{
    "status": "pass|warn|fail",
    "time_context": "适用时间范围",
    "note": "简要说明"
  }},
  "completeness": {{
    "status": "pass|warn|fail",
    "missing_context": "缺失内容描述",
    "suggestion": "补充建议"
  }},
  "overall": "approved|review|rejected",
  "action": "integrate|review|reject",
  "review_reason": "如果 action=review，说明原因"
}}
```

评审规则：
- 简单的想法、一句话洞察 → overall = "approved"，不阻塞
- 只有置信度不足时才标记为 "review"
- 不要过度评审
- 只输出 JSON，不要有其他解释。"""
    return prompt


def call_llm(prompt: str) -> str:
    """调用 LLM 生成评审结果"""
    try:
        import litellm
    except ImportError:
        raise ImportError("litellm not installed. Run: pip install litellm")

    api_key = LLM_API_KEY or os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("Missing API key")

    response = litellm.completion(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        api_key=api_key,
        max_tokens=2048,
        temperature=0.2,
    )
    return response.choices[0].message.content


def parse_review_json(json_text: str) -> dict[str, Any]:
    """解析 LLM 返回的评审 JSON"""
    # 提取 JSON 块
    if "```json" in json_text:
        json_text = json_text.split("```json")[1].split("```")[0]
    elif "```" in json_text:
        json_text = json_text.split("```")[1].split("```")[0]

    try:
        return json.loads(json_text.strip())
    except Exception as e:
        raise ValueError(f"Failed to parse JSON: {e}\nRaw output:\n{json_text}")


# ─── 主入口 ────────────────────────────────────────────────────────

def review_card(
    card: CardDraft,
    existing_cards: list[str] = None,
) -> ReviewResult | None:
    """评审单张卡片

    Args:
        card: 卡片草稿
        existing_cards: 已有知识库内容列表（用于冗余度检测）

    Returns:
        ReviewResult，如果内容简单直接通过则返回 None
    """
    # 简单的想法、一句话洞察直接通过，不需要评审
    content_len = len(card.content.strip())
    if content_len < 100 and not any(keyword in card.content for keyword in
                                      ["注意", "警告", "过时", "废弃", "错误", "问题"]):
        return None  # 直接通过

    # 构建 prompt
    prompt = build_review_prompt(card, existing_cards)

    # 调用 LLM
    llm_response = call_llm(prompt)

    # 解析 JSON
    review_data = parse_review_json(llm_response)

    # 构建维度结果
    def parse_dimension(data: dict) -> DimensionResult | None:
        if not data:
            return None
        return DimensionResult(
            status=data.get("status", "pass"),
            note=data.get("note"),
            evidence=data.get("evidence"),
        )

    def parse_redundancy(data: dict) -> RedundancyResult | None:
        if not data:
            return None
        similar_cards = [
            RedundancySimilarCard(
                path=c.get("path", ""),
                similarity=c.get("similarity", 0.0),
                overlap=c.get("overlap"),
            )
            for c in data.get("similar_cards", [])
        ]
        return RedundancyResult(
            status=data.get("status", "pass"),
            similar_cards=similar_cards,
            suggestion=data.get("suggestion"),
        )

    def parse_placement(data: dict) -> PlacementResult | None:
        if not data:
            return None
        return PlacementResult(
            suggested_path=data.get("suggested_path", ""),
            strategy=data.get("strategy", "new"),
            reasoning=data.get("reasoning"),
            confidence=data.get("confidence", "medium"),
        )

    dimensions = ReviewDimensions(
        credibility=parse_dimension(review_data.get("credibility")),
        noise=parse_dimension(review_data.get("noise")),
        redundancy=parse_redundancy(review_data.get("redundancy")),
        placement=parse_placement(review_data.get("placement")),
        timeliness=parse_dimension(review_data.get("timeliness")),
        completeness=parse_dimension(review_data.get("completeness")),
    )

    return ReviewResult(
        card_id=card.id,
        overall=review_data.get("overall", "approved"),
        dimensions=dimensions,
        action=review_data.get("action", "integrate"),
        review_reason=review_data.get("review_reason"),
    )


def should_review(result: ReviewResult | None) -> bool:
    """判断是否需要生成 review 报告"""
    if result is None:
        return False  # 简单内容，直接通过
    return result.action == "review"
