"""
MyRAG Extract — 阶段 1: 从各种源文件提取纯文本 + 元数据

支持：PDF, HTML, DOCX, Markdown, 纯文本
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from .schemas import ExtractOutput, InputMeta, Section
from .config import NEWDATA_DIR, PROJECT_ROOT


# ─── 提取器注册表 ──────────────────────────────────────────────────

EXTRACTORS = {}


def register_extractor(source_type: str):
    """装饰器：注册提取器"""
    def decorator(func):
        EXTRACTORS[source_type] = func
        return func
    return decorator


# ─── 通用工具 ──────────────────────────────────────────────────────

def detect_source_type(file_path: Path) -> str:
    """根据扩展名检测源类型"""
    suffix = file_path.suffix.lower()
    mapping = {
        ".pdf": "pdf",
        ".html": "html",
        ".htm": "html",
        ".docx": "docx",
        ".md": "md",
        ".txt": "txt",
    }
    return mapping.get(suffix, "unknown")


def compute_hash(file_path: Path) -> str:
    """计算文件 SHA256 哈希（前 16 位）"""
    import hashlib
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


# ─── PDF 提取器 ────────────────────────────────────────────────────

@register_extractor("pdf")
def extract_pdf(file_path: Path) -> ExtractOutput:
    """用 pdfplumber 提取 PDF 文本 + 结构"""
    try:
        import pdfplumber
    except ImportError:
        raise ImportError("pdfplumber not installed. Run: pip install pdfplumber")

    file_hash = compute_hash(file_path)
    meta = InputMeta(
        source_path=str(file_path.relative_to(PROJECT_ROOT)),
        source_type="pdf",
        file_hash=file_hash,
        title=file_path.stem,
    )

    text_parts = []
    sections = []

    with pdfplumber.open(file_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

            # 提取章节标题（基于字体大小 heuristics）
            if hasattr(page, "chars") and page.chars:
                page_sections = _extract_pdf_sections(page, page_num)
                sections.extend(page_sections)

    text = "\n\n".join(text_parts)
    return ExtractOutput(meta=meta, text=text, sections=sections)


def _extract_pdf_sections(page, page_num: int) -> list[Section]:
    """从 PDF 页面提取章节标题（基于字体大小 heuristics）"""
    sections = []
    chars = getattr(page, "chars", [])
    if not chars:
        return sections

    # 按 y 坐标排序（从上到下）
    chars_sorted = sorted(chars, key=lambda c: (c.get("top", 0), c.get("x0", 0)))

    # 计算平均字体大小
    sizes = [c.get("size", 12) for c in chars_sorted if c.get("size")]
    if not sizes:
        return sections

    avg_size = sum(sizes) / len(sizes)

    # 字体大小 > 平均 1.5 倍的行可能是标题
    current_line = []
    current_y = None
    current_size = 0

    for char in chars_sorted:
        size = char.get("size", 12)
        y = char.get("top", 0)

        if current_y is not None and abs(y - current_y) > 2:
            # 新行
            if current_size > avg_size * 1.5 and current_line:
                heading_text = "".join(current_line).strip()
                if heading_text and len(heading_text) < 100:
                    sections.append(Section(
                        heading=heading_text,
                        level=2 if current_size > avg_size * 2 else 3,
                        start_line=page_num,
                    ))
            current_line = []
            current_size = 0

        current_line.append(char.get("text", ""))
        if size > current_size:
            current_size = size
        current_y = y

    return sections


# ─── HTML 提取器 ───────────────────────────────────────────────────

@register_extractor("html")
def extract_html(file_path: Path) -> ExtractOutput:
    """用 pandoc 将 HTML 转 Markdown，去除导航/广告/脚本"""
    file_hash = compute_hash(file_path)
    meta = InputMeta(
        source_path=str(file_path.relative_to(PROJECT_ROOT)),
        source_type="html",
        file_hash=file_hash,
        title=file_path.stem,
    )

    try:
        result = subprocess.run(
            ["pandoc", "-f", "html", "-t", "markdown", "--strip-comments",
             str(file_path)],
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )
        text = result.stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise RuntimeError(f"pandoc failed: {e}. Install pandoc or use manual extraction.")

    # 简单清洗：去除明显的导航/广告链接
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        # 跳过纯链接行（常见的导航/广告模式）
        if line.strip().startswith("[") and line.strip().endswith(")"):
            if "http" in line and len(line) < 200:
                continue
        cleaned.append(line)

    text = "\n".join(cleaned)
    return ExtractOutput(meta=meta, text=text)


# ─── DOCX 提取器 ───────────────────────────────────────────────────

@register_extractor("docx")
def extract_docx(file_path: Path) -> ExtractOutput:
    """用 pandoc 将 DOCX 转 Markdown，保留标题层级"""
    file_hash = compute_hash(file_path)
    meta = InputMeta(
        source_path=str(file_path.relative_to(PROJECT_ROOT)),
        source_type="docx",
        file_hash=file_hash,
        title=file_path.stem,
    )

    try:
        result = subprocess.run(
            ["pandoc", "-f", "docx", "-t", "markdown", str(file_path)],
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )
        text = result.stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise RuntimeError(f"pandoc failed: {e}. Install pandoc or use manual extraction.")

    # 提取章节结构（基于 Markdown 标题）
    sections = []
    for i, line in enumerate(text.split("\n"), 1):
        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            heading = line.lstrip("#").strip()
            sections.append(Section(
                heading=heading,
                level=level,
                start_line=i,
            ))

    return ExtractOutput(meta=meta, text=text, sections=sections)


# ─── Markdown 提取器 ───────────────────────────────────────────────

@register_extractor("md")
def extract_markdown(file_path: Path) -> ExtractOutput:
    """直接读取 Markdown 文件，保留 frontmatter"""
    file_hash = compute_hash(file_path)
    meta = InputMeta(
        source_path=str(file_path.relative_to(PROJECT_ROOT)),
        source_type="md",
        file_hash=file_hash,
        title=file_path.stem,
    )

    text = file_path.read_text(encoding="utf-8")

    # 提取章节结构
    sections = []
    for i, line in enumerate(text.split("\n"), 1):
        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            heading = line.lstrip("#").strip()
            sections.append(Section(
                heading=heading,
                level=level,
                start_line=i,
            ))

    return ExtractOutput(meta=meta, text=text, sections=sections)


@register_extractor("obsidian")
def extract_obsidian(file_path: Path) -> ExtractOutput:
    """读取 Obsidian 笔记，保留 wikilink 和 tag"""
    # 与 Markdown 提取器相同，但标记为 obsidian 类型
    output = extract_markdown(file_path)
    output.meta.source_type = "obsidian"
    return output


# ─── 纯文本提取器 ──────────────────────────────────────────────────

@register_extractor("txt")
def extract_text(file_path: Path) -> ExtractOutput:
    """直接读取纯文本"""
    file_hash = compute_hash(file_path)
    meta = InputMeta(
        source_path=str(file_path.relative_to(PROJECT_ROOT)),
        source_type="txt",
        file_hash=file_hash,
        title=file_path.stem,
    )
    text = file_path.read_text(encoding="utf-8")
    return ExtractOutput(meta=meta, text=text)


# ─── 主入口 ────────────────────────────────────────────────────────

def extract(file_path: Path) -> ExtractOutput:
    """提取文件内容，自动检测类型"""
    source_type = detect_source_type(file_path)
    if source_type == "unknown":
        raise ValueError(f"Unsupported file type: {file_path.suffix}")

    extractor = EXTRACTORS.get(source_type)
    if not extractor:
        raise ValueError(f"No extractor for type: {source_type}")

    return extractor(file_path)
