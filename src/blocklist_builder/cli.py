"""CLI for blocklist factory using Click."""

from __future__ import annotations

import json as json_module
from dataclasses import asdict
from pathlib import Path

import click

from .analyze import analyze_build
from .build import build
from .config import load_settings
from .firebog import sync_firebog
from .gate import run_gate
from .recommend import compute_recommendations


def _repo_root() -> Path:
    """Get repo root (assumes src/blocklist_builder/cli.py layout)."""
    return Path(__file__).resolve().parents[2]


@click.group()
@click.version_option()
def cli() -> None:
    """Blocklist Factory - Build and manage Pi-hole blocklists."""
    pass


@cli.command()
@click.option(
    "--no-fetch",
    is_flag=True,
    help="Do not download; use local files.",
)
@click.option(
    "--json",
    is_flag=True,
    help="Output stats as JSON.",
)
def build_cmd(no_fetch: bool, json: bool) -> None:
    """Build blocklists from sources."""
    root = _repo_root()
    try:
        settings = load_settings(root / "config")
        stats = build(root, settings, no_fetch=no_fetch)
        if json:
            click.echo(json_module.dumps(asdict(stats), indent=2))
        else:
            click.secho(f"✓ Unique domains: {stats.unique_domains}", fg="green")
            click.echo(f"  Parsed OK: {stats.parsed_ok} | Sanitized OK: {stats.sanitized_ok}")
            click.echo(f"  Reports: {root / 'dist' / 'reports'}")
    except Exception as e:
        click.secho(f"✗ Build failed: {e}", fg="red", err=True)
        raise SystemExit(1) from e


@cli.command()
def validate() -> None:
    """Validate configuration files."""
    root = _repo_root()
    try:
        settings = load_settings(root / "config")
        click.secho("✓ Config valid", fg="green")
        click.echo(f"  Sources: {len(settings.sources)}")
        click.echo(f"  Profiles: {len(settings.profiles.by_name)}")
        click.echo(f"  Policies precedence: {' > '.join(settings.policies.category_precedence)}")
    except Exception as e:
        click.secho(f"✗ Config error: {e}", fg="red", err=True)
        raise SystemExit(1) from e


@cli.command()
def report() -> None:
    """Show latest build statistics."""
    root = _repo_root()
    stats_json = root / "dist" / "reports" / "stats.json"
    if not stats_json.exists():
        click.secho("✗ No build stats found. Run 'build' first.", fg="red", err=True)
        raise SystemExit(1)
    try:
        data = json_module.loads(stats_json.read_text(encoding="utf-8"))
        click.echo(json_module.dumps(data, indent=2))
    except Exception as e:
        click.secho(f"✗ Error reading stats: {e}", fg="red", err=True)
        raise SystemExit(1) from e


@cli.command("gate")
@click.option(
    "--dist",
    "dist",
    type=click.Path(path_type=Path),
    default=Path("dist"),
    show_default=True,
    help="Build output directory to check.",
)
@click.option(
    "--previous",
    type=click.Path(path_type=Path),
    default=None,
    help="Previously published all.txt, for the drop check.",
)
@click.option(
    "--max-drop",
    type=click.FloatRange(0.0, 1.0),
    default=0.10,
    show_default=True,
    help="Largest tolerated shrink versus --previous, as a fraction.",
)
@click.option(
    "--allow-drop",
    is_flag=True,
    help="Skip the drop check (intentional large removal).",
)
@click.option(
    "--must-not-block",
    "must_not_block",
    type=click.Path(path_type=Path),
    default=Path("inputs/current_overrides/must_not_block.txt"),
    show_default=True,
    help="File of names that must not appear in, or be covered by, the built list.",
)
def gate_cmd(
    dist: Path,
    previous: Path | None,
    max_drop: float,
    allow_drop: bool,
    must_not_block: Path,
) -> None:
    """Check a finished build before it is published; exit 1 when it is not safe."""
    result = run_gate(dist, previous, max_drop, allow_drop, must_not_block)
    for note in result.notes:
        click.secho(f"  {note}", fg="yellow")
    if result.failures:
        for failure in result.failures:
            click.secho(f"✗ {failure}", fg="red", err=True)
        raise SystemExit(1)
    if result.previous is None:
        summary = f"domains={result.domains} previous=none"
    else:
        delta = (result.domains - result.previous) / result.previous
        summary = f"domains={result.domains} previous={result.previous} delta={delta:+.2%}"
    click.secho(f"✓ Gate passed: {summary}", fg="green")


@cli.command("sync-firebog")
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be done without writing files.",
)
def sync_firebog_cmd(dry_run: bool) -> None:
    """Sync Firebog blocklist catalog."""
    try:
        import requests  # noqa: F401
    except ImportError:
        click.secho(
            "✗ requests package required. Run: uv pip install requests",
            fg="red",
            err=True,
        )
        raise SystemExit(1) from None

    root = _repo_root()
    try:
        result = sync_firebog(root / "config", dry_run=dry_run)
        if "error" in result:
            click.secho(f"✗ {result['error']}", fg="red", err=True)
            raise SystemExit(1)
        click.secho("✓ Firebog sync complete", fg="green")
        for cat, count in result["by_category"].items():
            click.echo(f"  {cat}: {count} lists")
        click.echo(f"  Total sources generated: {result['sources_generated']}")
    except Exception as e:
        click.secho(f"✗ Sync failed: {e}", fg="red", err=True)
        raise SystemExit(1) from e


@cli.command()
def analyze() -> None:
    """Analyze build outputs for quality and errors."""
    root = _repo_root()
    dist_dir = root / "dist"
    if not dist_dir.exists():
        click.secho("✗ No dist/ found. Run 'build' first.", fg="red", err=True)
        raise SystemExit(1)
    try:
        settings = load_settings(root / "config")
        result = analyze_build(dist_dir, settings)
        if "error" in result:
            click.secho(f"✗ {result['error']}", fg="red", err=True)
            raise SystemExit(1)
        click.secho("✓ Analysis complete", fg="green")
        click.echo(f"  Total domains: {result['total_domains']}")
        click.echo(f"  Findings: {result['findings']}")
        click.echo(f"  High-discard sources: {result.get('high_discard_sources', 0)}")
        click.echo(f"  Overlap 2 sources: {result['overlap_2']}")
        click.echo(f"  Overlap 3+ sources: {result['overlap_3_plus']}")
        click.echo(f"  Report: {result['output_file']}")
    except Exception as e:
        click.secho(f"✗ Analysis failed: {e}", fg="red", err=True)
        raise SystemExit(1) from e


@cli.command()
def recommend() -> None:
    """Generate recommendations for loading blocklists in Pi-hole."""
    root = _repo_root()
    dist_dir = root / "dist"
    if not dist_dir.exists():
        click.secho("✗ No dist/ found. Run 'build' first.", fg="red", err=True)
        raise SystemExit(1)
    try:
        settings = load_settings(root / "config")
        result = compute_recommendations(dist_dir, settings)
        if "error" in result:
            click.secho(f"✗ {result['error']}", fg="red", err=True)
            raise SystemExit(1)
        click.secho("✓ Recommendations generated", fg="green")
        click.echo(f"  Total domains: {result['total_domains']}")
        click.echo(f"  High-value sources: {result['high_value_sources']}")
        click.echo(f"  Moderate-value sources: {result['moderate_value_sources']}")
        click.echo(f"  Low-value sources: {result['low_value_sources']}")
        click.echo(f"  Top sources: {', '.join(result['top_sources'][:3])}")
        click.echo(f"  Report: {result['output_file']}")
    except Exception as e:
        click.secho(f"✗ Recommendation failed: {e}", fg="red", err=True)
        raise SystemExit(1) from e


def main(argv: list[str] | None = None) -> int:
    """Main entry point for testing."""
    try:
        cli(argv, standalone_mode=False)
        return 0
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1
    except Exception:
        return 1


if __name__ == "__main__":
    cli()
