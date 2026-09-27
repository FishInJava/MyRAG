"""
MyRAG Pipeline — V1 Skeleton

Usage:
    python pipeline.py                  # 处理 inbox/ 中所有新增文件
    python pipeline.py inbox/xxx.pdf   # 处理指定文件
"""

import sys
import hashlib
from pathlib import Path
from datetime import datetime

# ─── Configuration ───────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INBOX_DIR = PROJECT_ROOT / "inbox"
INTERMEDIATE_DIR = PROJECT_ROOT / "intermediate"
VAULT_DIR = PROJECT_ROOT / "myObsidian"
PROCESSED_LOG = PROJECT_ROOT / "inbox" / ".processed"

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


def stage_atomize(extract_dir: Path) -> Path:
    """Stage 2: Atomize text into knowledge cards."""
    print(f"[2/5] ATOMIZE: {extract_dir.name}")
    # TODO: Implement LLM-based atomization
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


def stage_integrate(approved_path: Path):
    """Stage 4: Integrate approved cards into myObsidian."""
    print(f"[4/5] INTEGRATE")
    # TODO: Implement myObsidian integration
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

    try:
        extract_dir = stage_extract(source_path)
        atomize_dir = stage_atomize(extract_dir)
        approved_path, review_path = stage_review(atomize_dir)
        stage_integrate(approved_path)
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
        # Process all new files in inbox/
        if not INBOX_DIR.exists():
            print(f"Inbox not found: {INBOX_DIR}")
            print("Create it with: mkdir inbox")
            return

        files = [f for f in INBOX_DIR.iterdir()
                 if f.is_file() and not f.name.startswith(".")]
        if not files:
            print("No files to process in inbox/")
            return

        for f in files:
            process_file(f)


if __name__ == "__main__":
    main()
