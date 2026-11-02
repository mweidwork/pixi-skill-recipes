"""Expected exceptions raised by the command line interface.

All errors that should be reported to a user without a traceback inherit from
:class:`SkillRecipesError`. The CLI maps these exceptions to a non-zero exit
code and prints a concise message.
"""

from __future__ import annotations


class SkillRecipesError(Exception):
    """Base class for expected command failures.

    Attributes:
        exit_code: Process exit code used when the error reaches the CLI.
    """

    exit_code = 1


class ConfigError(SkillRecipesError):
    """The repository or channel configuration is invalid."""


class RecipeError(SkillRecipesError):
    """A skill recipe is missing or invalid."""


class BuildError(SkillRecipesError):
    """rattler-build failed or produced no artifacts."""


class ChannelError(SkillRecipesError):
    """A channel operation could not be completed."""


class StorageError(SkillRecipesError):
    """An S3 operation failed."""
