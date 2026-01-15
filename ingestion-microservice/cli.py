"""Command-line interface for ingestion pipeline."""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone

import typer  # type: ignore

from app.pipeline import main_async
from app.logger import logger
from config import settings

# Rich console for better output formatting
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

console = Console() if RICH_AVAILABLE else None

app = typer.Typer(
    name="Ingestion Pipeline",
    help="Async document ingestion pipeline for ChromaDB",
)


@app.command()
def ingest(
    rebuild: bool = typer.Option(
        False,
        "--rebuild",
        help="Delete collection before ingesting (idempotent mode)",
    ),
    purge: bool = typer.Option(
        False,
        "--purge",
        help="Delete entire ChromaDB directory before ingesting",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Process documents but don't store in ChromaDB",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose logging output",
    ),
) -> None:
    """Run the ingestion pipeline.
    
    Processes documents from RAW_PDFS and RAW_TXTS directories,
    stores chunks and embeddings in ChromaDB.
    
    Examples:
    
      # Standard ingestion
      $ python -m ingestion_microservice ingest
      
      # Rebuild collection from scratch
      $ python -m ingestion_microservice ingest --rebuild
      
      # Preview without storing
      $ python -m ingestion_microservice ingest --dry-run --verbose
    """
    start_time = datetime.now(timezone.utc)
    
    # Print header
    if RICH_AVAILABLE:
        console.print(
            Panel(
                "[bold cyan]Ingestion Pipeline[/bold cyan]",
                title="[bold]Start[/bold]",
                expand=False,
            )
        )
    else:
        print(f"\n{'='*60}")
        print("Ingestion Pipeline")
        print(f"{'='*60}\n")
    
    # Log startup info
    mode_flags = []
    if rebuild:
        mode_flags.append("REBUILD")
    if purge:
        mode_flags.append("PURGE")
    if dry_run:
        mode_flags.append("DRY-RUN")
    
    mode_str = f" [{', '.join(mode_flags)}]" if mode_flags else ""
    
    logger.info(f"Ingestion Service v0.1.0{mode_str}")
    logger.info(f"Environment: {settings.APP_ENV}")
    logger.info(f"Raw data: {settings.RAW_DATA_DIR}")
    logger.info(f"ChromaDB: {settings.CHROMA_PATH}")
    logger.info(f"Batch size: {settings.INGEST_BATCH_SIZE}")
    logger.info(f"Workers: {settings.MAX_WORKERS}")
    logger.info(f"Verbose: {verbose}")
    
    try:
        asyncio.run(
            main_async(
                rebuild=rebuild,
                purge=purge,
                dry_run=dry_run,
                verbose=verbose,
            )
        )
        
        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        if RICH_AVAILABLE:
            console.print(
                Panel(
                    f"[bold green]✓ Ingestion completed successfully[/bold green]\n"
                    f"Elapsed: {elapsed:.2f}s",
                    title="[bold]Complete[/bold]",
                    expand=False,
                )
            )
        else:
            print(f"\n{'='*60}")
            print("✓ Ingestion completed successfully")
            print(f"Elapsed: {elapsed:.2f}s")
            print(f"{'='*60}\n")
        
        sys.exit(0)
    except KeyboardInterrupt:
        logger.warning("Ingestion interrupted by user")
        if RICH_AVAILABLE:
            console.print("\n[yellow]⚠ Ingestion interrupted[/yellow]")
        else:
            print("\n⚠ Ingestion interrupted")
        sys.exit(130)
    except Exception as e:
        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
        logger.error(f"✗ Ingestion failed: {e}")
        
        if RICH_AVAILABLE:
            console.print(
                Panel(
                    f"[bold red]✗ Ingestion failed[/bold red]\n"
                    f"Error: {str(e)}\n"
                    f"Elapsed: {elapsed:.2f}s",
                    title="[bold]Failed[/bold]",
                    expand=False,
                )
            )
        else:
            print(f"\n{'='*60}")
            print(f"✗ Ingestion failed: {e}")
            print(f"Elapsed: {elapsed:.2f}s")
            print(f"{'='*60}\n")
        
        sys.exit(1)


@app.command()
def config() -> None:
    """Show current configuration."""
    settings_table = [
        ("APP_NAME", settings.APP_NAME),
        ("APP_ENV", settings.APP_ENV),
        ("LOG_LEVEL", settings.LOG_LEVEL),
        ("", ""),
        ("RAW_DATA_DIR", str(settings.RAW_DATA_DIR)),
        ("CHROMA_PATH", str(settings.CHROMA_PATH)),
        ("", ""),
        ("COLLECTION", settings.CHROMA_COLLECTION_NAME),
        ("DISTANCE", settings.CHROMA_DISTANCE),
        ("EMB_MODEL", settings.EMB_MODEL),
        ("OLLAMA_HOST", settings.OLLAMA_HOST),
        ("EMBEDDING_TIMEOUT", f"{settings.EMBEDDING_TIMEOUT}s"),
        ("EMBEDDING_RETRIES", str(settings.EMBEDDING_RETRIES)),
        ("", ""),
        ("CHUNK_TOKENS", str(settings.CHUNK_TOKENS)),
        ("CHUNK_OVERLAP_TOKENS", str(settings.CHUNK_OVERLAP_TOKENS)),
        ("CHUNK_CHARS", str(settings.chunk_chars)),
        ("CHUNK_OVERLAP_CHARS", str(settings.chunk_overlap_chars)),
        ("", ""),
        ("BATCH_SIZE", str(settings.INGEST_BATCH_SIZE)),
        ("MAX_WORKERS", str(settings.MAX_WORKERS)),
        ("HASH_ALGO", settings.HASH_ALGO),
    ]
    
    if RICH_AVAILABLE:
        table = Table(title="Configuration")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")
        
        for key, value in settings_table:
            if key == "":
                table.add_row()
            else:
                table.add_row(key, value)
        
        console.print(table)
    else:
        print(f"\n{'='*60}")
        print("Ingestion Service Configuration")
        print(f"{'='*60}\n")
        
        for key, value in settings_table:
            if key:
                print(f"  {key}: {value}")
            else:
                print()
        print(f"{'='*60}\n")


@app.command()
def health(verbose: bool = typer.Option(False, "--verbose/-q", help="Detailed health output")) -> None:
    """Check if all dependencies are accessible.
    
    Validates:
    - Raw data directories
    - ChromaDB paths
    - Ollama connectivity
    """
    if RICH_AVAILABLE:
        console.print(Panel("[bold cyan]Health Check[/bold cyan]", expand=False))
    else:
        print("\nHealth Check:\n")
    
    checks = {
        "Raw PDFs": settings.get_raw_pdfs_dir(),
        "Raw TXTs": settings.get_raw_txts_dir(),
        "ChromaDB": settings.CHROMA_PATH,
    }
    
    results = []
    all_ok = True
    
    for name, path in checks.items():
        exists = path.exists() if isinstance(path, Path) else Path(path).exists()
        status = "✓" if exists else "✗"
        results.append((name, str(path), status))
        all_ok = all_ok and exists
    
    if RICH_AVAILABLE:
        table = Table(title="Directories" if not verbose else None)
        table.add_column("Component", style="cyan")
        if verbose:
            table.add_column("Path", style="dim")
        table.add_column("Status", style="green" if all_ok else "red")
        
        for name, path, status in results:
            if verbose:
                table.add_row(name, path, status)
            else:
                table.add_row(name, status)
        
        console.print(table)
        
        status_msg = "[bold green]✓ All checks passed[/bold green]"
        if not all_ok:
            status_msg = "[bold red]✗ Some checks failed[/bold red]"
        
        console.print(Panel(status_msg, expand=False))
    else:
        for name, path, status in results:
            print(f"  {name}: {status}")
            if verbose:
                print(f"    Path: {path}")
        
        print()
        print(f"Overall: {'✓ All checks passed' if all_ok else '✗ Some checks failed'}")
        print()


def main() -> None:
    """Entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
