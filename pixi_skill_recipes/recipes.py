"""Read, validate, and scaffold skill recipes."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError
from ruamel.yaml.scalarstring import DoubleQuotedScalarString

from .errors import RecipeError
from .versioning import parse_version

SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True)
class Recipe:
    """A parsed skill recipe.

    Args:
        skill: Skill directory name.
        path: Path to ``recipe.yaml``.
        package_name: Conda package name such as ``agent-skill-code-review``.
        version: Current package version.
    """

    skill: str
    path: Path
    package_name: str
    version: str


def list_skills(recipes_dir: Path) -> list[str]:
    """List skill names that have a recipe.

    Args:
        recipes_dir: Directory containing skill subdirectories.

    Returns:
        Sorted skill directory names.
    """
    if not recipes_dir.is_dir():
        return []
    return sorted(path.parent.name for path in recipes_dir.glob("*/recipe.yaml"))


def load_recipe(recipes_dir: Path, skill: str) -> Recipe:
    """Load and validate a skill recipe.

    Args:
        recipes_dir: Directory containing skill subdirectories.
        skill: Skill directory name.

    Returns:
        The parsed recipe metadata.

    Raises:
        RecipeError: If the recipe is missing, malformed, or has an invalid version.
    """
    path = recipes_dir / skill / "recipe.yaml"
    if not path.is_file():
        raise RecipeError(f"recipe not found: {path}")

    data = _load_yaml(path)
    context = data.get("context") or {}
    package = data.get("package") or {}
    if not isinstance(context, dict) or not isinstance(package, dict):
        raise RecipeError(f"{path} must contain 'context' and 'package' tables")

    recipe_skill = str(context.get("skill") or skill)
    package_name = str(package.get("name") or f"agent-skill-{recipe_skill}")
    if "${{" in package_name:
        package_name = f"agent-skill-{recipe_skill}"

    raw_version = package.get("version")
    if raw_version is None:
        raise RecipeError(f"{path} is missing package.version")
    version = str(raw_version)
    parse_version(version)

    return Recipe(
        skill=recipe_skill,
        path=path,
        package_name=package_name,
        version=version,
    )


def set_recipe_version(path: Path, version: str) -> None:
    """Write a new version into a recipe while preserving its formatting.

    Args:
        path: Path to ``recipe.yaml``.
        version: New version string.

    Raises:
        RecipeError: If the version is invalid or the recipe lacks a package table.
    """
    parse_version(version)
    yaml = _yaml()
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.load(handle)

    if not isinstance(data, dict):
        raise RecipeError(f"{path} does not contain a YAML mapping")
    package = data.get("package")
    if not isinstance(package, dict):
        raise RecipeError(f"{path} is missing a package table")

    package["version"] = DoubleQuotedScalarString(version)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        yaml.dump(data, handle)


def scaffold_skill(
    recipes_dir: Path,
    skill: str,
    *,
    description: str | None = None,
    force: bool = False,
) -> tuple[Path, Path]:
    """Create a new skill directory with ``SKILL.md`` and ``recipe.yaml``.

    Args:
        recipes_dir: Directory containing skill subdirectories.
        skill: New skill name.
        description: Optional short description used in frontmatter and metadata.
        force: Whether to overwrite files in an existing skill directory.

    Returns:
        The created ``SKILL.md`` and ``recipe.yaml`` paths.

    Raises:
        RecipeError: If the name is invalid or the directory exists without ``force``.
    """
    validate_skill_name(skill)
    skill_dir = recipes_dir / skill
    if skill_dir.exists() and not force:
        raise RecipeError(f"skill directory already exists: {skill_dir}")

    skill_dir.mkdir(parents=True, exist_ok=True)
    title = skill.replace("-", " ").title()
    summary = description or f"{title} guidelines for AI coding agents"

    skill_path = skill_dir / "SKILL.md"
    recipe_path = skill_dir / "recipe.yaml"
    skill_path.write_text(_skill_markdown(skill, summary), encoding="utf-8")
    recipe_path.write_text(_recipe_yaml(skill, summary), encoding="utf-8")
    return skill_path, recipe_path


def validate_skill_name(skill: str) -> None:
    """Validate that a skill name is lowercase and hyphen-separated.

    Args:
        skill: Skill name to validate.

    Raises:
        RecipeError: If the name contains unsupported characters.
    """
    if not SKILL_NAME_RE.fullmatch(skill):
        raise RecipeError(
            f"invalid skill name '{skill}': use lowercase letters, digits, and hyphens"
        )


def _skill_markdown(skill: str, summary: str) -> str:
    """Render a starter ``SKILL.md`` document.

    Args:
        skill: Skill name.
        summary: Short description used in YAML frontmatter.

    Returns:
        Markdown content for a new skill.
    """
    title = skill.replace("-", " ").title()
    return (
        "---\n"
        f"name: {skill}\n"
        "description: >\n"
        f"  {summary}\n"
        "---\n"
        "\n"
        f"# {title}\n"
        "\n"
        "Explain when the agent should use this skill and the workflow it should follow.\n"
        "\n"
        "## Guidelines\n"
        "\n"
        "- Describe the first concrete step.\n"
        "- Describe validation or verification steps.\n"
        "- Link to any bundled references or scripts.\n"
    )


def _recipe_yaml(skill: str, summary: str) -> str:
    """Render a starter ``recipe.yaml`` document.

    Args:
        skill: Skill name.
        summary: Short package summary.

    Returns:
        YAML content for a new recipe.
    """
    return (
        "context:\n"
        f"  skill: {skill}\n"
        "\n"
        "package:\n"
        "  name: agent-skill-${{ skill }}\n"
        '  version: "0.1.0"\n'
        "\n"
        "source:\n"
        "  path: .\n"
        "\n"
        "build:\n"
        "  noarch: generic\n"
        "  script:\n"
        '    - mkdir -p "${PREFIX}/share/agent-skills/${{ skill }}"\n'
        '    - cp "${RECIPE_DIR}/SKILL.md" '
        '"${PREFIX}/share/agent-skills/${{ skill }}/SKILL.md"\n'
        "\n"
        "tests:\n"
        "  - package_contents:\n"
        "      files:\n"
        f"        - share/agent-skills/{skill}/SKILL.md\n"
        "\n"
        "about:\n"
        f"  summary: {json.dumps(summary)}\n"
        "  license: MIT\n"
    )


def _load_yaml(path: Path) -> dict[str, Any]:
    """Read a YAML mapping from disk.

    Args:
        path: YAML file to read.

    Returns:
        The parsed mapping.

    Raises:
        RecipeError: If the file cannot be parsed or is not a mapping.
    """
    yaml = _yaml()
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.load(handle)
    except YAMLError as exc:
        raise RecipeError(f"failed to read {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise RecipeError(f"{path} does not contain a YAML mapping")
    return data


def _yaml() -> YAML:
    """Create a round-trip YAML parser configured for recipe formatting.

    Returns:
        A configured ruamel YAML instance.
    """
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml
