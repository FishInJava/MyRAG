"""
MyRAG Schemas — 数据结构定义 + 校验

基于 spec/schema.yaml，提供 Python 数据类和校验函数。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


# ─── 1. 输入文件元数据 ─────────────────────────────────────────────

@dataclass
class InputMeta:
    source_path: str
    source_type: str  # pdf, html, docx, txt, md, obsidian
    file_hash: str
    title: Optional[str] = None
    author: Optional[str] = None
    date: Optional[str] = None
    extracted_at: str = field(default_factory=lambda: datetime.now().isoformat())


# ─── 2. 提取输出 ───────────────────────────────────────────────────

@dataclass
class Section:
    heading: str
    level: int
    start_line: int
    end_line: Optional[int] = None


@dataclass
class ExtractOutput:
    meta: InputMeta
    text: str = ""
    sections: list[Section] = field(default_factory=list)


# ─── 3. 卡片草稿 ───────────────────────────────────────────────────

@dataclass
class SourceRef:
    file: str
    location: str
    quote: Optional[str] = None


@dataclass
class CardDraft:
    id: str
    title: str
    domain: str
    subtopic: str
    content: str = ""
    source_refs: list[SourceRef] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


# ─── 4. 评审结果 ───────────────────────────────────────────────────

@dataclass
class DimensionResult:
    status: str  # pass, warn, fail
    note: Optional[str] = None
    evidence: Optional[str] = None


@dataclass
class RedundancySimilarCard:
    path: str
    similarity: float
    overlap: Optional[str] = None


@dataclass
class RedundancyResult:
    status: str  # pass, warn, fail
    similar_cards: list[RedundancySimilarCard] = field(default_factory=list)
    suggestion: Optional[str] = None


@dataclass
class PlacementResult:
    suggested_path: str
    strategy: str  # merge, new, split, adjacent
    reasoning: Optional[str] = None
    confidence: str  # high, medium, low


@dataclass
class ReviewDimensions:
    credibility: Optional[DimensionResult] = None
    noise: Optional[DimensionResult] = None
    redundancy: Optional[RedundancyResult] = None
    placement: Optional[PlacementResult] = None
    timeliness: Optional[DimensionResult] = None
    completeness: Optional[DimensionResult] = None


@dataclass
class ReviewResult:
    card_id: str
    overall: str  # approved, review, rejected
    dimensions: ReviewDimensions = field(default_factory=ReviewDimensions)
    action: str = "integrate"  # integrate, review, reject
    review_reason: Optional[str] = None


# ─── 5. 整合输出 ───────────────────────────────────────────────────

@dataclass
class CreatedFile:
    path: str
    card_count: int


@dataclass
class UpdatedFile:
    path: str
    added_sections: list[str] = field(default_factory=list)


@dataclass
class MergedContent:
    target_path: str
    source_cards: list[str] = field(default_factory=list)


@dataclass
class LinkCreated:
    from_: str
    to: str


@dataclass
class IntegrationError:
    card_id: str
    error: str


@dataclass
class IntegrateOutput:
    created: list[CreatedFile] = field(default_factory=list)
    updated: list[UpdatedFile] = field(default_factory=list)
    merged: list[MergedContent] = field(default_factory=list)
    links_created: list[LinkCreated] = field(default_factory=list)
    errors: list[IntegrationError] = field(default_factory=list)


# ─── 6. Vault 文件 frontmatter ─────────────────────────────────────

@dataclass
class VaultFrontmatter:
    domain: str
    subtopic: str
    created: str = ""
    updated: str = ""
    sources: list[str] = field(default_factory=list)
    confidence: str = "medium"
    reviewed: bool = False
    tags: list[str] = field(default_factory=list)


# ─── 7. Review 报告 ────────────────────────────────────────────────

@dataclass
class ReviewItem:
    card_id: str
    issue: str = ""
    suggestion: str = ""
    evidence: str = ""


@dataclass
class ReviewSummary:
    total_cards: int = 0
    approved: int = 0
    review: int = 0
    rejected: int = 0


@dataclass
class ReviewReport:
    date: str = ""
    source_file: str = ""
    summary: ReviewSummary = field(default_factory=ReviewSummary)
    items: list[ReviewItem] = field(default_factory=list)


# ─── 工具函数 ──────────────────────────────────────────────────────

def compute_file_hash(path: Path) -> str:
    """计算文件的 SHA256 哈希（前 16 位）"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def is_processed(file_hash_val: str, processed_log: Path) -> bool:
    """检查文件是否已处理"""
    if not processed_log.exists():
        return False
    return file_hash_val in processed_log.read_text().splitlines()


def mark_processed(file_hash_val: str, processed_log: Path):
    """记录已处理的文件哈希"""
    with open(processed_log, "a") as f:
        f.write(f"{file_hash_val}\n")
