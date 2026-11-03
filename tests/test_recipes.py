"""Tests for recipe scaffolding, loading, and version updates."""

from __future__ import annotations

from pathlib import Path

import pytest
from pixi_skill_recipes.errors import RecipeError
from pixi_skill_recipes.recipes import (
    list_skills,
    load_recipe,
    scaffold_skill,
    set_recipe_version,
    validate_skill_name,
)


def test_scaffold_skill_creates_valid_recipe(tmp_path: Path) -> None:
    """Scaffolding creates a skill that can be loaded again."""
    recipes_dir = tmp_path / "recipes"

    skill_path, recipe_path = scaffold_skill(
        recipes_dir,
        "data-engineering",
        description="Data pipeline guidance: quality and reliability.",
    )

    assert skill_path.is_file()
    assert recipe_path.is_file()
    assert list_skills(recipes_dir) == ["data-engineering"]

    recipe = load_recipe(recipes_dir, "data-engineering")
    assert recipe.skill == "data-engineering"
    assert recipe.package_name == "agent-skill-data-engineering"
    assert recipe.version == "0.1.0"


def test_scaffold_rejects_duplicate_skill(tmp_path: Path) -> None:
    """Scaffolding an existing skill fails unless force is set."""
    recipes_dir = tmp_path / "recipes"
    scaffold_skill(recipes_dir, "code-review")

    with pytest.raises(RecipeError, match="already exists"):
        scaffold_skill(recipes_dir, "code-review")


def test_scaffold_force_overwrites(tmp_path: Path) -> None:
    """The force flag allows updating scaffolded files."""
    recipes_dir = tmp_path / "recipes"
    scaffold_skill(recipes_dir, "code-review")

    skill_path, _ = scaffold_skill(
        recipes_dir,
        "code-review",
        description="Updated description",
        force=True,
    )

    assert "Updated description" in skill_path.read_text(encoding="utf-8")


@pytest.mark.parametrize("name", ["Bad Name", "UPPER", "with_underscore", "trailing-"])
def test_invalid_skill_names_are_rejected(name: str) -> None:
    """Skill names must be lowercase hyphen-separated identifiers."""
    with pytest.raises(RecipeError, match="invalid skill name"):
        validate_skill_name(name)


def test_set_recipe_version_preserves_recipe(tmp_path: Path) -> None:
    """Version updates preserve the rest of the recipe and quoted style."""
    recipes_dir = tmp_path / "recipes"
    _, recipe_path = scaffold_skill(recipes_dir, "code-review")

    set_recipe_version(recipe_path, "0.2.0rc1")

    text = recipe_path.read_text(encoding="utf-8")
    assert 'version: "0.2.0rc1"' in text
    assert load_recipe(recipes_dir, "code-review").version == "0.2.0rc1"
