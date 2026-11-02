"""Scaffold a new agent skill from the templates in this skill's assets folder.

Usage:
    python scripts/scaffold_skill.py my-skill
    python scripts/scaffold_skill.py my-skill --dir path/to/skills --with-scripts
    python scripts/scaffold_skill.py my-skill --all

The script creates a valid SKILL.md and optional scripts/, references/, and
assets/ directories. Existing files are only overwritten with --force.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
RESERVED_WORDS = ("anthropic", "claude")
SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = SCRIPT_DIR.parent / "assets"

TEMPLATES = {
    "skill": ("SKILL.md.template", "SKILL.md"),
    "script": ("script.py.template", "scripts/example.py"),
    "reference": ("reference.md.template", "references/guide.md"),
    "asset": ("asset.txt.template", "assets/template.txt"),
}


def normalize_description(description: str) -> str:
    return " ".join(description.split())


def render(template: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", value)
    return template


def build_files(name: str, description: str, resources: set[str]) -> dict[Path, str]:
    title = name.replace("-", " ").title()
    values = {"name": name, "title": title, "description": description}
    selected = ["skill", *sorted(resources)]
    files: dict[Path, str] = {}

    for template_key in selected:
        template_name, output_name = TEMPLATES[template_key]
        template_path = TEMPLATE_DIR / template_name
        if not template_path.is_file():
            raise FileNotFoundError(f"Template not found: {template_path}")
        content = template_path.read_text(encoding="utf-8")
        files[Path(output_name)] = render(content, values)

    return files


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaffold a new agent skill.")
    parser.add_argument("name", help="Skill name in lowercase-hyphen format")
    parser.add_argument("--dir", default=".", help="Parent directory for the skill (default: current directory)")
    parser.add_argument("--description", help="Skill description for the frontmatter")
    parser.add_argument("--with-scripts", action="store_true", help="Add a scripts/ example")
    parser.add_argument("--with-references", action="store_true", help="Add a references/ example")
    parser.add_argument("--with-assets", action="store_true", help="Add an assets/ example")
    parser.add_argument("--all", action="store_true", help="Add scripts/, references/, and assets/")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    args = parser.parse_args()

    if not NAME_RE.match(args.name):
        print("ERROR: name must use lowercase letters, numbers, and hyphens only.", file=sys.stderr)
        return 1
    for word in RESERVED_WORDS:
        if word in args.name.lower():
            print(f"ERROR: name must not contain the reserved word {word!r}.", file=sys.stderr)
            return 1

    resources: set[str] = set()
    if args.all:
        resources.update({"script", "reference", "asset"})
    if args.with_scripts:
        resources.add("script")
    if args.with_references:
        resources.add("reference")
    if args.with_assets:
        resources.add("asset")

    description = args.description or (
        f"Creates and applies the {args.name.replace('-', ' ')} workflow. "
        f"Use when the task requires {args.name.replace('-', ' ')} guidance."
    )
    description = normalize_description(description)
    if len(description) > 1024:
        print("ERROR: description must be 1,024 characters or fewer.", file=sys.stderr)
        return 1

    skill_dir = Path(args.dir).resolve() / args.name
    if skill_dir.exists() and not args.force:
        print(f"ERROR: {skill_dir} already exists; use --force to overwrite files.", file=sys.stderr)
        return 1

    try:
        files = build_files(args.name, description, resources)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    for relative_path, content in files.items():
        destination = skill_dir / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8", newline="\n")
        print(f"created {destination}")

    print(f"\nNext: review {skill_dir / 'SKILL.md'}, then run:")
    print(f"  python {SCRIPT_DIR / 'validate_skill.py'} {skill_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
