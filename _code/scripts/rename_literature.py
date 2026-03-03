"""Rename literature notes to match the new filename convention and update wiki links."""

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from engram_r.search_interface import _make_literature_filename

vault = Path(__file__).resolve().parent.parent.parent
lit_dir = vault / "_research" / "literature"

# 1. Compute renames
renames = []
for f in sorted(lit_dir.glob("*.md")):
    if f.name.startswith("_"):
        continue
    text = f.read_text()
    if not text.startswith("---"):
        continue
    end = text.find("---", 3)
    if end == -1:
        continue
    fm = yaml.safe_load(text[3:end])
    if not isinstance(fm, dict):
        continue
    result_dict = {
        "year": fm.get("year", ""),
        "authors": fm.get("authors", []),
        "title": fm.get("title", ""),
    }
    new_name = _make_literature_filename(result_dict)
    if f.name != new_name:
        renames.append((f.name, new_name))

if not renames:
    print("No renames needed.")
    sys.exit(0)

# 2. Collect all .md files in vault for link updates
all_md = list(vault.rglob("*.md"))
print(f"Scanning {len(all_md)} markdown files for link updates...")

# 3. For each rename: move file, update all wiki links
for old_name, new_name in renames:
    old_stem = old_name.removesuffix(".md")
    new_stem = new_name.removesuffix(".md")

    old_path = lit_dir / old_name
    new_path = lit_dir / new_name

    if not old_path.exists():
        print(f"SKIP (missing): {old_name}")
        continue

    # Rename file
    old_path.rename(new_path)

    # Update wiki links in all files
    link_updates = 0
    for md_file in all_md:
        if not md_file.exists():
            continue
        try:
            content = md_file.read_text()
        except Exception:
            continue
        if old_stem not in content:
            continue
        new_content = content.replace(f"[[{old_stem}]]", f"[[{new_stem}]]")
        new_content = new_content.replace(f"[[{old_stem}|", f"[[{new_stem}|")
        if new_content != content:
            md_file.write_text(new_content)
            link_updates += 1

    suffix = f" ({link_updates} links updated)" if link_updates else ""
    print(f"OK: {old_name} -> {new_name}{suffix}")

print(f"\nDone: {len(renames)} files renamed")
