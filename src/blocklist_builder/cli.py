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
