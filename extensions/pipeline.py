"""
MyRAG Pipeline — V1 实现

Usage:
    python pipeline.py                  # 处理 newData/ 中所有新增文件
    python pipeline.py newData/xxx.pdf   # 处理指定文件
"""

import sys
import hashlib
import json
from pathlib import Path
from datetime import datetime

# ─── Configuration ───────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
NEWDATA_DIR = PROJECT_ROOT / "newData"
INTERMEDIATE_DIR = PROJECT_ROOT / "intermediate"
MYOBSIDIAN_DIR = PROJECT_ROOT / "myObsidian"
PROCESSED_LOG = PROJECT_ROOT / "newData" / ".processed"
TEMPLATES_DIR = PROJECT_ROOT / "template"

# ─── Output Contract (用户自定义的输出规范) ────────────────────────

def load_output_contract() -> dict[str, str]:
    """Load all template files from template/ as the output contract."""
    contract = {}
    if not TEMPLATES_DIR.exists():
        return contract
    for f in sorted(TEMPLATES_DIR.rglob("*.md")):
        contract[f.name] = f.read_text(encoding="utf-8")
    return contract


# ─── Helpers ─────────────────────────────────────────────────────

def file_hash(path: Path) -> str:
    """Calculate SHA256 of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def is_processed(file_hash_val: str) -> bool:
    """Check if file has already been processed."""
    if not PROCESSED_LOG.exists():
        return False
    return file_hash_val in PROCESSED_LOG.read_text().splitlines()


def mark_processed(file_hash_val: str):
    """Record processed file hash."""
    with open(PROCESSED_LOG, "a") as f:
        f.write(f"{file_hash_val}\n")


def save_intermediate(data, filename: str, directory: Path):
    """保存中间数据到文件"""
    directory.mkdir(parents=True, exist_ok=True)
    filepath = directory / filename
    if hasattr(data, "__dataclass_fields__"):
        # dataclass → JSON
        import dataclasses
        data_dict = dataclasses.asdict(data)
        filepath.write_text(json.dumps(data_dict, ensure_ascii=False, indent=2), encoding="utf-8")
    elif isinstance(data, list):
        # list → JSON
        import dataclasses
        data_list = [dataclasses.asdict(item) if hasattr(item, "__dataclass_fields__") else item for item in data]
        filepath.write_text(json.dumps(data_list, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        filepath.write_text(str(data), encoding="utf-8")
    return filepath


# ─── Pipeline Stages ─────────────────────────────────────────────

def stage_extract(source_path: Path) -> Path:
    """Stage 1: Extract text + metadata from source file."""
    print(f"[1/5] EXTRACT: {source_path.name}")

    from .extract import extract
    extract_output = extract(source_path)

    # 保存到 intermediate
    extract_dir = INTERMEDIATE_DIR / "extract" / extract_output.meta.file_hash
    extract_dir.mkdir(parents=True, exist_ok=True)

    save_intermediate(extract_output.meta, "meta.json", extract_dir)
    save_intermediate(extract_output, "extract.json", extract_dir)

    # 保存纯文本
    (extract_dir / "text.txt").write_text(extract_output.text, encoding="utf-8")

    print(f"       → {extract_dir} ({len(extract_output.text)} chars)")
    return extract_dir


def stage_atomize(extract_dir: Path, output_contract: dict[str, str]) -> Path:
    """Stage 2: Atomize text into knowledge cards."""
    print(f"[2/5] ATOMIZE: {extract_dir.name}")

    from .atomize import atomize
    from .schemas import ExtractOutput
    from .config import config

    # 读取提取结果
    import json
    extract_data = json.loads((extract_dir / "extract.json").read_text(encoding="utf-8"))
    extract_output = ExtractOutput(
        meta=extract_data["meta"],
        text=extract_data.get("text", ""),
    )

    # 执行原子化
    cards = atomize(extract_output, output_contract)

    # 保存结果
    atomize_dir = INTERMEDIATE_DIR / "atomize" / extract_dir.name
    atomize_dir.mkdir(parents=True, exist_ok=True)
    save_intermediate(cards, "cards.json", atomize_dir)

    print(f"       → {atomize_dir} ({len(cards)} cards)")
    return atomize_dir


def stage_review(atomize_dir: Path) -> tuple[Path, Path]:
    """Stage 3: Review cards, classify as approved/review/rejected."""
    print(f"[3/5] REVIEW: {atomize_dir.name}")

    from .review import review_card, should_review
    from .schemas import CardDraft, ReviewResult, ReviewReport, ReviewSummary, ReviewItem
    import json

    # 读取卡片
    cards_data = json.loads((atomize_dir / "cards.json").read_text(encoding="utf-8"))
    cards = [
        CardDraft(
            id=c["id"],
            title=c["title"],
            domain=c["domain"],
            subtopic=c["subtopic"],
            content=c.get("content", ""),
            source_refs=c.get("source_refs", []),
            tags=c.get("tags", []),
        )
        for c in cards_data
    ]

    # 评审每张卡片
    approved = []
    review_items = []
    summary = ReviewSummary(total_cards=len(cards))

    for card in cards:
        try:
            result = review_card(card)
        except Exception as e:
            # LLM 调用失败，标记为 review
            print(f"       ⚠️  Review failed for {card.id}: {e}")
            result = ReviewResult(
                card_id=card.id,
                overall="review",
                action="review",
                review_reason=f"评审失败: {str(e)}",
            )

        if result is None or result.action == "integrate":
            # 直接通过
            approved.append(card)
            summary.approved += 1
        elif result.action == "reject":
            summary.rejected += 1
        else:
            # 需要 review
            summary.review += 1
            review_items.append(ReviewItem(
                card_id=card.id,
                issue=result.review_reason or "需要人工决定",
                suggestion=result.dimensions.placement.suggested_path if result.dimensions.placement else "",
                evidence=result.dimensions.credibility.evidence if result.dimensions.credibility else "",
            ))

    # 保存结果
    review_dir = INTERMEDIATE_DIR / "review" / atomize_dir.name
    review_dir.mkdir(parents=True, exist_ok=True)

    save_intermediate(approved, "cards_approved.json", review_dir)

    # 生成 review 报告（如果有）
    if review_items:
        report = ReviewReport(
            date=datetime.now().isoformat(),
            source_file=atomize_dir.name,
            summary=summary,
            items=review_items,
        )
        # 保存为 Markdown
        review_md_lines = [
            f"# Review: {atomize_dir.name} — {report.date}",
            "",
            "## 摘要",
            f"- 处理卡片: {summary.total_cards}",
            f"- 直接入库: {summary.approved}",
            f"- 待你决定: {summary.review}",
            f"- 建议删除: {summary.rejected}",
            "",
            "---",
            "",
        ]
        for i, item in enumerate(review_items, 1):
            review_md_lines.extend([
                f"### {i}. {item.issue}",
                f"**来源**: `{atomize_dir.name}` → \"{item.card_id}\"",
                f"**问题**: {item.issue}",
                f"**建议**: {item.suggestion}",
                f"**证据**: {item.evidence}",
                "",
            ])

        (review_dir / "cards_review.md").write_text("\n".join(review_md_lines), encoding="utf-8")
        print(f"       ⚠️  {summary.review} items need review")
    else:
        print(f"       ✅ All {summary.approved} cards approved")

    return review_dir / "cards_approved.json", review_dir / "cards_review.md"


def stage_integrate(approved_path: Path, output_contract: dict[str, str]):
    """Stage 4: Integrate approved cards into myObsidian."""
    print(f"[4/5] INTEGRATE")

    from .integrate import integrate
    from .schemas import CardDraft
    import json

    # 读取通过评审的卡片
    cards_data = json.loads(approved_path.read_text(encoding="utf-8"))
    cards = [
        CardDraft(
            id=c["id"],
            title=c["title"],
            domain=c["domain"],
            subtopic=c["subtopic"],
            content=c.get("content", ""),
            source_refs=c.get("source_refs", []),
            tags=c.get("tags", []),
        )
        for c in cards_data
    ]

    if not cards:
        print("       No cards to integrate")
        return

    # 逐张整合
    for card in cards:
        try:
            result = integrate(card, None, output_contract)
            if result.created:
                for f in result.created:
                    print(f"       ✅ Created: {f.path}")
            if result.updated:
                for f in result.updated:
                    print(f"       🔄 Updated: {f.path}")
            if result.errors:
                for e in result.errors:
                    print(f"       ❌ Error: {e.error}")
        except Exception as e:
            print(f"       ❌ Failed to integrate {card.id}: {e}")


def stage_index():
    """Stage 5: Update TOC and indices."""
    print(f"[5/5] INDEX")

    from .index import index
    index()
    print(f"       → myObsidian/_meta/ updated")


# ─── Main ────────────────────────────────────────────────────────

def process_file(source_path: Path):
    """Run full pipeline on a single source file."""
    print(f"\n{'='*60}")
    print(f"Processing: {source_path.name}")
    print(f"{'='*60}\n")

    fh = file_hash(source_path)
    if is_processed(fh):
        print(f"Already processed (hash: {fh}), skipping.")
        return

    # Load user's output contract (must happen before any LLM call)
    output_contract = load_output_contract()
    if output_contract:
        print(f"📋 Output contract loaded: {len(output_contract)} template files")
    else:
        print(f"⚠️  No output contract found at {TEMPLATES_DIR}")

    try:
        extract_dir = stage_extract(source_path)
        atomize_dir = stage_atomize(extract_dir, output_contract)
        approved_path, review_path = stage_review(atomize_dir)
        stage_integrate(approved_path, output_contract)
        stage_index()

        mark_processed(fh)
        print(f"\n✅ Done: {source_path.name}")
        if review_path.exists() and review_path.stat().st_size > 10:
            print(f"⚠️  Review file: {review_path}")

        # Git commit
        try:
            import subprocess
            subprocess.run(
                ["git", "add", "-A"],
                cwd=PROJECT_ROOT,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "commit", "-m", f"feat: process {source_path.name}"],
                cwd=PROJECT_ROOT,
                check=True,
                capture_output=True,
            )
            print(f"📝 Git committed")
        except Exception as e:
            print(f"⚠️  Git commit failed: {e}")

    except Exception as e:
        print(f"\n❌ Error processing {source_path.name}: {e}")
        import traceback
        traceback.print_exc()


def main():
    if len(sys.argv) > 1:
        # Process specific file(s)
        for arg in sys.argv[1:]:
            path = Path(arg)
            if path.exists():
                process_file(path)
            else:
                print(f"File not found: {arg}")
    else:
        # Process all new files in newData/
        if not NEWDATA_DIR.exists():
            print(f"newData not found: {NEWDATA_DIR}")
            print("Create it with: mkdir newData")
            return

        files = [f for f in NEWDATA_DIR.iterdir()
                 if f.is_file() and not f.name.startswith(".")]
        if not files:
            print("No files to process in newData/")
            return

        for f in files:
            process_file(f)


if __name__ == "__main__":
    main()
