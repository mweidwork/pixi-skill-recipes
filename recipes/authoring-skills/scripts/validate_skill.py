"""Validate an agent skill against the SKILL.md authoring contract.

Usage:
    python scripts/validate_skill.py path/to/skill
    python scripts/validate_skill.py path/to/skill/SKILL.md --strict
    python scripts/validate_skill.py path/to/skill --json

The validator uses only the Python standard library so it can run in restricted
agent environments. It checks the frontmatter contract, body length, resource
links, path style, referenced files, and Python script syntax.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
XML_TAG_RE = re.compile(r"<[^>]+>")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
RESOURCE_RE = re.compile(r"(?<![\w./-])((?:scripts|references|assets)/[A-Za-z0-9_.\-/]+)")
WINDOWS_PATH_RE = re.compile(r"(?:scripts|references|assets)\\[A-Za-z0-9_.\-\\]+")
RESERVED_WORDS = ("anthropic", "claude")
MAX_BODY_LINES = 500
MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024


def parse_frontmatter(text: str) -> tuple[dict[str, str] | None, str, list[str]]:
    """Parse the simple YAML subset used by SKILL.md frontmatter."""
    errors: list[str] = []
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, text, ["SKILL.md must start with a YAML frontmatter block delimited by '---'."]

    end = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end = index
            break
    if end is None:
        return None, text, ["SKILL.md frontmatter is missing the closing '---' delimiter."]

    data: dict[str, str] = {}
    body = "\n".join(lines[end + 1 :])
    index = 1
    while index < end:
        raw = lines[index]
        if not raw.strip() or raw.lstrip().startswith("#"):
            index += 1
            continue
        if raw[0].isspace():
            errors.append(f"Unexpected indented frontmatter line {index + 1}: {raw.strip()!r}")
            index += 1
            continue
        if ":" not in raw:
            errors.append(f"Frontmatter line {index + 1} is not a 'key: value' pair: {raw.strip()!r}")
            index += 1
            continue

        key, rest = raw.split(":", 1)
        key = key.strip()
        rest = rest.strip()
        if rest in {">", "|", ">-", "|-", ">+", "|+"}:
            style = rest[0]
            chunks: list[str] = []
            index += 1
            while index < end and (lines[index].startswith((" ", "\t")) or not lines[index].strip()):
                chunks.append(lines[index].strip())
                index += 1
            while chunks and not chunks[-1]:
                chunks.pop()
            if style == ">":
                data[key] = " ".join(chunk for chunk in chunks if chunk)
            else:
                data[key] = "\n".join(chunks)
            continue

        data[key] = rest.strip("\"'")
        index += 1

    return data, body, errors


def iter_link_targets(markdown: str) -> list[str]:
    targets: list[str] = []
    for match in LINK_RE.finditer(markdown):
        target = match.group(1).strip()
        target = target.split("#", 1)[0].strip()
        if not target or target.startswith(("http://", "https://", "mailto:", "//", "{{")):
            continue
        targets.append(target)
    return targets


def iter_resource_mentions(markdown: str) -> list[str]:
    return [match.group(1).rstrip(".,;:") for match in RESOURCE_RE.finditer(markdown)]


def check_description(description: str, errors: list[str], warnings: list[str]) -> None:
    if not description:
        errors.append("Frontmatter field 'description' is required and must not be empty.")
        return
    if len(description) > MAX_DESCRIPTION_LENGTH:
        errors.append(
            f"Description is {len(description)} characters; maximum is {MAX_DESCRIPTION_LENGTH}."
        )
    if XML_TAG_RE.search(description):
        errors.append("Description must not contain XML tags.")
    lowered = description.lower()
    if lowered.startswith(("i ", "i'", "you ", "we ")) or "you can" in lowered or "i can" in lowered:
        warnings.append("Description should be written in the third person (what it does and when to use it).")
    if len(description.split()) < 8:
        warnings.append("Description is very short; include specific triggers and key capabilities.")


def check_name(name: str, skill_dir: Path, errors: list[str], warnings: list[str]) -> None:
    if not name:
        errors.append("Frontmatter field 'name' is required and must not be empty.")
        return
    if len(name) > MAX_NAME_LENGTH:
        errors.append(f"Name is {len(name)} characters; maximum is {MAX_NAME_LENGTH}.")
    if not NAME_RE.match(name):
        errors.append("Name must use only lowercase letters, numbers, and hyphens, with no leading or trailing hyphen.")
    if XML_TAG_RE.search(name):
        errors.append("Name must not contain XML tags.")
    for word in RESERVED_WORDS:
        if word in name.lower():
            errors.append(f"Name must not contain the reserved word {word!r}.")
    if name != skill_dir.name:
        warnings.append(f"Skill directory is {skill_dir.name!r} but frontmatter name is {name!r}.")


def check_body(body: str, errors: list[str], warnings: list[str]) -> None:
    line_count = len(body.splitlines())
    if line_count > MAX_BODY_LINES:
        warnings.append(
            f"SKILL.md body has {line_count} lines; keep it under {MAX_BODY_LINES} and move detail into references/."
        )


def check_resources(
    skill_dir: Path,
    markdown: str,
    errors: list[str],
    warnings: list[str],
) -> None:
    for match in WINDOWS_PATH_RE.finditer(markdown):
        errors.append(f"Use forward slashes in resource paths, not {match.group(0)!r}.")

    referenced: set[Path] = set()
    for target in iter_link_targets(markdown) + iter_resource_mentions(markdown):
        path = Path(target)
        if path.is_absolute():
            continue
        referenced.add(path)
        if not (skill_dir / path).exists():
            errors.append(f"Referenced resource does not exist: {target}")

    references_dir = skill_dir / "references"
    if references_dir.is_dir():
        for reference in sorted(references_dir.rglob("*.md")):
            relative = reference.relative_to(skill_dir)
            if relative not in referenced:
                warnings.append(f"Reference file is not linked directly from SKILL.md: {relative.as_posix()}")


def check_scripts(skill_dir: Path, errors: list[str], warnings: list[str]) -> None:
    scripts_dir = skill_dir / "scripts"
    if not scripts_dir.is_dir():
        return
    for script in sorted(scripts_dir.rglob("*.py")):
        relative = script.relative_to(skill_dir).as_posix()
        try:
            source = script.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(f"Script is not valid UTF-8: {relative}")
            continue
        try:
            tree = ast.parse(source, filename=relative)
        except SyntaxError as exc:
            errors.append(f"Python syntax error in {relative}:{exc.lineno}: {exc.msg}")
            continue
        if ast.get_docstring(tree) is None:
            warnings.append(f"Script has no module docstring: {relative}")


def validate(target: Path) -> tuple[list[str], list[str], Path]:
    errors: list[str] = []
    warnings: list[str] = []

    if target.is_file():
        skill_file = target
        skill_dir = target.parent
    else:
        skill_dir = target
        skill_file = target / "SKILL.md"

    if not skill_file.is_file():
        return [f"SKILL.md not found at {skill_file}"], warnings, skill_dir

    try:
        text = skill_file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return [f"SKILL.md is not valid UTF-8: {skill_file}"], warnings, skill_dir

    frontmatter, body, parse_errors = parse_frontmatter(text)
    errors.extend(parse_errors)
    if frontmatter is None:
        return errors, warnings, skill_dir

    name = frontmatter.get("name", "")
    description = frontmatter.get("description", "")

    check_name(name, skill_dir, errors, warnings)
    check_description(description, errors, warnings)
    check_body(body, errors, warnings)
    check_resources(skill_dir, text, errors, warnings)
    check_scripts(skill_dir, errors, warnings)

    return errors, warnings, skill_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an agent skill directory or SKILL.md file.")
    parser.add_argument("target", help="Skill directory or path to SKILL.md")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args()

    errors, warnings, skill_dir = validate(Path(args.target))

    if args.json:
        print(
            json.dumps(
                {
                    "skill": skill_dir.name,
                    "valid": not errors and (not args.strict or not warnings),
                    "errors": errors,
                    "warnings": warnings,
                },
                indent=2,
            )
        )
    else:
        for message in errors:
            print(f"ERROR: {message}")
        for message in warnings:
            print(f"WARNING: {message}")
        if not errors and not warnings:
            print(f"OK: {skill_dir} is valid.")
        elif not errors:
            print(f"PASS: {skill_dir} has {len(warnings)} warning(s).")
        else:
            print(f"FAIL: {skill_dir} has {len(errors)} error(s) and {len(warnings)} warning(s).")

    if errors:
        return 1
    if args.strict and warnings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
