"""Command-line interface for filegetter."""

import logging

import click

from . import __version__
from .cmds.project import ConfigError, FilegetterBuilder


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=level,
        force=True,
    )


@click.group()
@click.version_option(version=__version__, prog_name="filegetter")
def cli():
    """filegetter: bulk file collection from public data sources."""


@cli.command()
@click.option(
    "--projectpath", "-p", default=None, help="Project directory (default: current directory)."
)
@click.option(
    "--verbose", "-v", is_flag=True, default=False, help="Verbose output with debug logging."
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="List pending downloads without fetching anything.",
)
@click.option(
    "--limit", type=int, default=None, help="Download at most N pending files in this run."
)
@click.option(
    "--refresh",
    is_flag=True,
    default=False,
    help="Re-read the source file instead of the cached allfiles.csv.",
)
def run(projectpath, verbose, dry_run, limit, refresh):
    """Execute the file collection project."""
    configure_logging(verbose)
    try:
        builder = FilegetterBuilder(projectpath)
    except ConfigError as e:
        raise click.ClickException(str(e))
    stats = builder.run(dry_run=dry_run, limit=limit, refresh=refresh)
    if stats.get("failed", 0) > 0:
        click.get_current_context().exit(1)
