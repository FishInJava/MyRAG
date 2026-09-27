"""
MyRAG Index — 阶段 5: 维护知识库索引

更新 myObsidian/_meta/ 下的全局索引和 TOC。
"""

from __future__ import annotations

from pathlib import Path
from datetime import date

from .config import MYOBSIDIAN_DIR


def update_global_toc():
    """更新全局 TOC（已由 integrate.py 的 update_toc 维护，此处做最终整理）"""
    meta_dir = MYOBSIDIAN_DIR / "_meta"
    meta_dir.mkdir(parents=True, exist_ok=True)

    # 更新 _meta/README.md
    readme_path = meta_dir / "README.md"
    today = date.today().isoformat()

    # 扫描所有领域
    domains = {}
    if MYOBSIDIAN_DIR.exists():
        for domain_dir in sorted(MYOBSIDIAN_DIR.iterdir()):
            if domain_dir.name.startswith("_") or not domain_dir.is_dir():
                continue
            subtopics = []
            for f in sorted(domain_dir.rglob("*.md")):
                if f.name.startswith("_") or f.name.startswith("."):
                    continue
                subtopics.append(f"  - [[{domain_dir.name}/{f.stem}|{f.stem}]]")
            if subtopics:
                domains[domain_dir.name] = "\n".join(subtopics)

    # 生成 README
    readme_lines = [
        "# MyRAG 知识库索引",
        "",
        f"> 最后更新: {today}",
        "",
        "## 领域",
        "",
    ]
    for domain, files in sorted(domains.items()):
        readme_lines.append(f"### {domain}")
        readme_lines.append("")
        readme_lines.append(files)
        readme_lines.append("")

    readme_path.write_text("\n".join(readme_lines), encoding="utf-8")


def index() -> None:
    """执行索引更新"""
    update_global_toc()
