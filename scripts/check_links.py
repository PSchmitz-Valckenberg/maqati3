#!/usr/bin/env python3
"""Check relative links and anchor headings in Markdown documentation."""

import re
import sys
from pathlib import Path


def slugify(text: str) -> str:
    """Convert heading text to GitHub Markdown anchor slug."""
    text = text.strip().lower()
    # Remove markdown formatting characters like backticks, links, bold, code
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[`*_{}\[\]()#+!.,?:;\"'\/]", "", text)
    text = re.sub(r"\s+", "-", text)
    return text.strip("-")


def get_headings(file_path: Path) -> set[str]:
    """Extract anchor slugs for all headings in a markdown file."""
    if not file_path.exists():
        return set()
    headings = set()
    for line in file_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line.startswith("#"):
            heading_text = line.lstrip("#").strip()
            headings.add(slugify(heading_text))
    return headings


def check_markdown_links(repo_root: Path) -> list[str]:
    """Scan all markdown files for broken relative links and heading anchors."""
    errors = []
    md_files = sorted(repo_root.glob("**/*.md"))

    # Regex for [label](target)
    link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

    for md_file in md_files:
        # Skip node_modules, .git, venv
        if any(part in md_file.parts for part in (".git", "node_modules", ".venv", ".next")):
            continue

        text = md_file.read_text(encoding="utf-8", errors="ignore")
        for match in link_pattern.finditer(text):
            label, target = match.groups()
            target = target.strip()

            # Ignore external protocols and mailto
            if target.startswith(("http://", "https://", "mailto:")):
                continue

            target_file_part = target.split("#")[0]
            anchor_part = target.split("#")[1] if "#" in target else None

            # Self-reference anchor
            if not target_file_part and anchor_part:
                headings = get_headings(md_file)
                if anchor_part not in headings:
                    errors.append(f"{md_file.relative_to(repo_root)}: anchor #{anchor_part} not found")
                continue

            # File path reference
            resolved_file = (md_file.parent / target_file_part).resolve()
            if not resolved_file.exists():
                errors.append(
                    f"{md_file.relative_to(repo_root)}: linked target '{target}' does not exist"
                )
            elif anchor_part and resolved_file.suffix == ".md":
                headings = get_headings(resolved_file)
                if anchor_part not in headings:
                    errors.append(
                        f"{md_file.relative_to(repo_root)}: anchor #{anchor_part} not found in {resolved_file.relative_to(repo_root)}"
                    )

    return errors


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    errors = check_markdown_links(repo_root)

    if errors:
        print(f"Found {len(errors)} broken relative link(s):")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("All markdown relative links and anchors verified successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
