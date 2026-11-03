"""Build skill recipes with ``rattler-build``."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .channel import PACKAGE_EXTENSIONS
from .errors import BuildError
from .recipes import Recipe

IGNORED_OUTPUT_DIRS = {"bld", "build", "src_cache"}


@dataclass(frozen=True)
class BuildResult:
    """Artifacts produced by a recipe build.

    Args:
        recipe: Recipe that was built.
        artifacts: Package files produced by the build.
        output_dir: Directory passed to ``rattler-build``.
    """

    recipe: Recipe
    artifacts: list[Path]
    output_dir: Path


class Builder:
    """Run ``rattler-build`` for a single recipe.

    Args:
        executable: Optional path to ``rattler-build``. Defaults to the executable
            found on ``PATH``.
        verbose: Whether to stream subprocess output to the terminal.
        runner: Subprocess runner, injectable for tests.
    """

    def __init__(
        self,
        executable: str | None = None,
        *,
        verbose: bool = False,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ) -> None:
        """Initialize the builder and resolve its executable."""
        self.executable = executable or shutil.which("rattler-build") or "rattler-build"
        self.verbose = verbose
        self.runner = runner

    def build(self, recipe: Recipe, output_dir: Path) -> BuildResult:
        """Build a recipe and return its package artifacts.

        Args:
            recipe: Recipe to build.
            output_dir: Directory that receives build output.

        Returns:
            The build result, including every matching package file.

        Raises:
            BuildError: If rattler-build fails or produces no matching artifacts.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        command = [
            self.executable,
            "build",
            "--recipe",
            str(recipe.path),
            "--output-dir",
            str(output_dir),
        ]
        result = self.runner(
            command,
            check=False,
            capture_output=not self.verbose,
            text=True,
        )
        if result.returncode != 0:
            output = (result.stderr or result.stdout or "").strip()
            raise BuildError(
                f"rattler-build failed for {recipe.skill}" + (f": {output}" if output else "")
            )

        artifacts = find_artifacts(output_dir, recipe)
        if not artifacts:
            raise BuildError(
                f"rattler-build produced no artifacts for {recipe.package_name}"
                f" {recipe.version} in {output_dir}"
            )
        return BuildResult(recipe=recipe, artifacts=artifacts, output_dir=output_dir)


def find_artifacts(output_dir: Path, recipe: Recipe) -> list[Path]:
    """Find package files for a specific recipe and version.

    Args:
        output_dir: Directory containing rattler-build output.
        recipe: Recipe whose artifacts should be returned.

    Returns:
        Matching package files sorted by path.
    """
    prefix = f"{recipe.package_name}-{recipe.version}-"
    artifacts: list[Path] = []
    if not output_dir.is_dir():
        return artifacts

    for candidate in output_dir.rglob("*"):
        if not candidate.is_file():
            continue
        if candidate.parent.name in IGNORED_OUTPUT_DIRS:
            continue
        if candidate.name.startswith(prefix) and candidate.name.endswith(PACKAGE_EXTENSIONS):
            artifacts.append(candidate)

    return sorted(artifacts)
