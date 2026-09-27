"""
MyRAG Integrate — 阶段 4: 将评审通过的卡片整合到 myObsidian/

职责：
- 确定目标路径（domain/subtopic.md）
- 检查已有文件，决定新建/合并/补充
- 写入文件（含 frontmatter + TOC + 内容）
- 更新 TOC 索引
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .schemas import (
    CardDraft,
    ReviewResult,
    IntegrateOutput,
    CreatedFile,
    UpdatedFile,
    MergedContent,
    LinkCreated,
    IntegrationError,
    VaultFrontmatter,
)
from .config import (
    PROJECT_ROOT,
    MYOBSIDIAN_DIR,
    LLM_MODEL,
    LLM_API_KEY,
)


# ─── 输出契约加载 ──────────────────────────────────────────────────

def load_output_contract() -> dict[str, str]:
    """从 template/ 加载输出契约"""
    from .atomize import load_output_contract
    return load_output_contract()


# ─── Prompt 构建 ───────────────────────────────────────────────────

def build_integrate_prompt(card: CardDraft, existing_files: list[str]) -> str:
    """构建整合 prompt"""
    existing_context = ""
    if existing_files:
        existing_context = "\n\n## 已有文件列表\n" + "\n".join(
            f"- {f}" for f in existing_files[:20]
        )

    prompt = f"""你是一个知识库管理员，负责决定一张卡片应该放在知识库的哪个位置。

## 任务

根据卡片内容，判断它应该：
1. **新建** 一个新文件（domain/subtopic.md）
2. **合并** 到已有文件（追加到合适位置）
3. **补充** 到已有文件（在已有文件的某个章节下添加内容）

## 卡片信息

**标题**：{card.title}
**领域**：{card.domain}
**子主题**：{card.subtopic}
**内容**：
{card.content[:500]}{"..." if len(card.content) > 500 else ""}

**来源**：{', '.join(ref.file for ref in card.source_refs)}{existing_context}

## 输出格式

```json
{{
  "strategy": "new|merge|supplement",
  "target_path": "domain/subtopic.md",
  "reasoning": "一句话说明",
  "section": "要加入的章节名（如果是 merge/supplement）",
  "confidence": "high|medium|low"
}}
```

只输出 JSON，不要有其他解释。"""
    return prompt


def call_llm(prompt: str) -> str:
    """调用 LLM 生成响应"""
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
        max_tokens=1024,
        temperature=0.2,
    )
    return response.choices[0].message.content


def parse_integrate_json(json_text: str) -> dict[str, Any]:
    """解析 LLM 返回的整合 JSON"""
    if "```json" in json_text:
        json_text = json_text.split("```json")[1].split("```")[0]
    elif "```" in json_text:
        json_text = json_text.split("```")[1].split("```")[0]

    try:
        return json.loads(json_text.strip())
    except Exception as e:
        raise ValueError(f"Failed to parse JSON: {e}\nRaw output:\n{json_text}")


# ─── 文件操作 ──────────────────────────────────────────────────────

def get_existing_files() -> list[str]:
    """获取 myObsidian/ 中已有文件列表"""
    if not MYOBSIDIAN_DIR.exists():
        return []

    files = []
    for f in MYOBSIDIAN_DIR.rglob("*.md"):
        if f.name.startswith("_") or f.name.startswith("."):
            continue
        rel_path = f.relative_to(MYOBSIDIAN_DIR)
        files.append(str(rel_path))
    return sorted(files)


def read_existing_file(rel_path: str) -> str | None:
    """读取已有文件内容"""
    file_path = MYOBSIDIAN_DIR / rel_path
    if not file_path.exists():
        return None
    return file_path.read_text(encoding="utf-8")


def write_vault_file(
    rel_path: str,
    content: str,
    frontmatter: VaultFrontmatter,
    output_contract: dict[str, str],
) -> Path:
    """写入 myObsidian/ 文件（含 frontmatter + TOC + 内容）"""
    file_path = MYOBSIDIAN_DIR / rel_path
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # 构建 frontmatter
    from datetime import date
    today = date.today().isoformat()

    fm_lines = [
        "---",
        f"domain: {frontmatter.domain}",
        f"subtopic: {frontmatter.subtopic}",
        f"created: {frontmatter.created or today}",
        f"updated: {today}",
        f"sources:",
    ]
    for src in frontmatter.sources:
        fm_lines.append(f"  - {src}")
    fm_lines.append(f"confidence: {frontmatter.confidence}")
    fm_lines.append(f"reviewed: {str(frontmatter.reviewed).lower()}")
    if frontmatter.tags:
        fm_lines.append("tags:")
        for tag in frontmatter.tags:
            fm_lines.append(f"  - {tag}")
    fm_lines.append("---")
    fm_lines.append("")

    # 检查输出契约中是否有 frontmatter 模板
    fm_template = output_contract.get("1笔记属性.md", "")
    if fm_template and "created:" in fm_template:
        # 使用模板的 frontmatter 格式
        import re
        fm_template = fm_template.strip()
        if fm_template.startswith("---"):
            # 替换模板中的占位符
            fm_content = fm_template.replace("{{date:YYYY-MM-DD}}", today)
            # 替换其他字段
            fm_content = re.sub(r"domain:.*", f"domain: {frontmatter.domain}", fm_content)
            fm_content = re.sub(r"subtopic:.*", f"subtopic: {frontmatter.subtopic}", fm_content)
            fm_content = re.sub(r"tags:\n  -", f"sources:\n  - {frontmatter.sources[0] if frontmatter.sources else ''}\n  tags:", fm_content)
            fm_lines = [fm_content, ""]

    full_content = "\n".join(fm_lines) + content
    file_path.write_text(full_content, encoding="utf-8")
    return file_path


def update_toc(rel_path: str, domain: str, subtopic: str):
    """更新 myObsidian/_meta/toc.yaml"""
    import yaml

    meta_dir = MYOBSIDIAN_DIR / "_meta"
    meta_dir.mkdir(parents=True, exist_ok=True)

    toc_path = meta_dir / "toc.yaml"
    toc_data = {}

    if toc_path.exists():
        try:
            toc_data = yaml.safe_load(toc_path.read_text(encoding="utf-8")) or {}
        except Exception:
            toc_data = {}

    # 确保 domain 存在
    if "domains" not in toc_data:
        toc_data["domains"] = {}

    if domain not in toc_data["domains"]:
        toc_data["domains"][domain] = {"subtopics": []}

    # 添加 subtopic（去重）
    subtopics = toc_data["domains"][domain]["subtopics"]
    if rel_path not in [s.get("path") for s in subtopics]:
        subtopics.append({
            "path": rel_path,
            "title": subtopic,
        })

    # 写入
    toc_path.write_text(
        yaml.dump(toc_data, allow_unicode=True, default_flow_style=False),
        encoding="utf-8",
    )


# ─── 主入口 ────────────────────────────────────────────────────────

def integrate(
    card: CardDraft,
    review_result: ReviewResult | None,
    output_contract: dict[str, str],
) -> IntegrateOutput:
    """将卡片整合到 myObsidian/

    Args:
        card: 卡片草稿
        review_result: 评审结果（可能为 None）
        output_contract: 输出契约

    Returns:
        整合结果
    """
    output = IntegrateOutput()
    existing_files = get_existing_files()

    try:
        # 确定目标路径
        if review_result and review_result.dimensions.placement:
            placement = review_result.dimensions.placement
            target_path = placement.suggested_path
            confidence = placement.confidence
        else:
            # 默认路径
            target_path = f"{card.domain}/{card.subtopic}.md"
            confidence = "medium"

        # 检查是否已有该文件
        if target_path in existing_files:
            # 已有文件，决定是合并还是新建带后缀的文件
            if confidence == "high":
                # 合并到已有文件
                existing_content = read_existing_file(target_path)
                if existing_content:
                    # 追加内容
                    new_section = f"\n\n## {card.title}\n\n{card.content}\n"
                    updated_content = existing_content + new_section

                    frontmatter = VaultFrontmatter(
                        domain=card.domain,
                        subtopic=card.subtopic,
                        sources=[ref.file for ref in card.source_refs],
                        confidence=review_result.dimensions.credibility.status if review_result and review_result.dimensions.credibility else "medium",
                        tags=card.tags,
                    )
                    write_vault_file(target_path, updated_content, frontmatter, output_contract)
                    output.updated.append(UpdatedFile(path=target_path, added_sections=[card.title]))
                else:
                    # 文件存在但无法读取，新建
                    _create_new_file(card, target_path, output_contract, output)
            else:
                # 置信度不够高，新建带后缀的文件
                new_path = f"{card.domain}/{card.subtopic}-{card.id}.md"
                _create_new_file(card, new_path, output_contract, output)
        else:
            # 新建文件
            _create_new_file(card, target_path, output_contract, output)

        # 更新 TOC
        update_toc(target_path, card.domain, card.subtopic)

    except Exception as e:
        output.errors.append(IntegrationError(card_id=card.id, error=str(e)))

    return output


def _create_new_file(
    card: CardDraft,
    rel_path: str,
    output_contract: dict[str, str],
    output: IntegrateOutput,
):
    """创建新文件"""
    frontmatter = VaultFrontmatter(
        domain=card.domain,
        subtopic=card.subtopic,
        sources=[ref.file for ref in card.source_refs],
        confidence="medium",
        tags=card.tags,
    )

    # 构建文件内容
    content = f"# {card.title}\n\n{card.content}\n"

    write_vault_file(rel_path, content, frontmatter, output_contract)
    output.created.append(CreatedFile(path=rel_path, card_count=1))
