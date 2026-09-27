"""
MyRAG Pipeline — V1 Skeleton

Usage:
    python pipeline.py                  # 处理 newData/ 中所有新增文件
    python pipeline.py newData/xxx.pdf   # 处理指定文件
"""

import sys
import hashlib
from pathlib import Path
from datetime import datetime

# ─── Configuration ───────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
NEWDATA_DIR = PROJECT_ROOT / "newData"
INTERMEDIATE_DIR = PROJECT_ROOT / "intermediate"
MYOBSIDIAN_DIR = PROJECT_ROOT / "myObsidian"
PROCESSED_LOG = PROJECT_ROOT / "newData" / ".processed"
TEMPLATES_DIR = PROJECT_ROOT / "00模板"

# ─── Output Contract (用户自定义的输出规范) ────────────────────────

def load_output_contract() -> dict[str, str]:
    """Load all template files from 00模板/ as the output contract.

    These files define the required format, style, and frontmatter for
    every markdown file the pipeline produces. They must be loaded before
    stages 2 (ATOMIZE) and 4 (INTEGRATE) and injected into the LLM prompt.

    Returns:
        dict mapping filename → full text content
    """
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


# ─── Pipeline Stages ─────────────────────────────────────────────

def stage_extract(source_path: Path) -> Path:
    """Stage 1: Extract text + metadata from source file."""
    print(f"[1/5] EXTRACT: {source_path.name}")
    # TODO: Implement extraction per source type
    # - PDF → pdfplumber
    # - HTML → pandoc
    # - DOCX → pandoc
    # - MD/TXT → direct read
    output_dir = INTERMEDIATE_DIR / "extract" / file_hash(source_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"       → {output_dir}")
    return output_dir


def stage_atomize(extract_dir: Path, output_contract: dict[str, str]) -> Path:
    """Stage 2: Atomize text into knowledge cards.

    Args:
        output_contract: 用户自定义输出规范（从 00模板/ 加载）
    """
    print(f"[2/5] ATOMIZE: {extract_dir.name}")
    # TODO: Implement LLM-based atomization
    # - Load output_contract templates as part of LLM prompt
    # - Apply HBZ style and frontmatter format from 00模板/
    output_dir = INTERMEDIATE_DIR / "atomize" / extract_dir.name
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"       → {output_dir}")
    return output_dir


def stage_review(atomize_dir: Path) -> tuple[Path, Path]:
    """Stage 3: Review cards, classify as approved/review/rejected."""
    print(f"[3/5] REVIEW: {atomize_dir.name}")
    # TODO: Implement multi-dimension review
    output_dir = INTERMEDIATE_DIR / "review" / atomize_dir.name
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"       → {output_dir}")
    return output_dir / "cards_approved.yaml", output_dir / "cards_review.md"


def stage_integrate(approved_path: Path, output_contract: dict[str, str]):
    """Stage 4: Integrate approved cards into myObsidian.

    Args:
        approved_path: 通过评审的卡片列表
        output_contract: 用户自定义输出规范（从 00模板/ 加载）
    """
    print(f"[4/5] INTEGRATE")
    # TODO: Implement myObsidian integration
    # - Load output_contract templates
    # - Apply HBZ style, frontmatter format, and symbol rules
    # - Determine target path (domain/subtopic.md)
    # - Check for existing files
    # - Embedding search for related cards
    # - Write/update myObsidian files
    pass


def stage_index():
    """Stage 5: Update TOC and indices."""
    print(f"[5/5] INDEX")
    # TODO: Update myObsidian/_meta/toc.yaml
    pass


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

    except Exception as e:
        print(f"\n❌ Error processing {source_path.name}: {e}")
        # Log error but continue


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
            print(f"Inbox not found: {NEWDATA_DIR}")
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
