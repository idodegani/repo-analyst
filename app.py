"""Repo Analyst - CLI Interface

A RAG-based code repository analyst for the httpx library.
Answer natural language questions with grounded answers and file:line citations.
"""

import sys
import logging
import click
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table
from rich.logging import RichHandler

from core.config import Config
from core.indexer import DocumentIndexer
from core.rag import RAGPipeline


# Configure logging with Rich handler for beautiful output
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True, show_path=False)]
)

# Set library loggers to WARNING to reduce noise
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("transformers").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

console = Console()


@click.group()
def cli():
    """Repo Analyst - Answer questions about the httpx repository.
    
    Commands:
      index        Build the FAISS index from the repository
      query        Answer a single question about the repository
      interactive  Start interactive query mode with conversation history
    """
    pass


@cli.command()
def index():
    """Build the FAISS index from the repository.
    
    This command processes all Python and Markdown files in the httpx
    repository, chunks them into semantic units, generates embeddings,
    and builds a FAISS index for semantic search.
    
    Example:
        python app.py index
    """
    try:
        console.print("\n[bold cyan]Repo Analyst - Indexing[/bold cyan]")
        console.print("=" * 60)
        
        config = Config()
        console.print("[green]OK[/green] Configuration loaded")
        
        indexer = DocumentIndexer(config)
        console.print("[green]OK[/green] Indexer initialized\n")
        
        indexer.index_repository()
        
        console.print("\n[bold green]SUCCESS: Indexing complete![/bold green]")
        console.print("You can now run queries with:")
        console.print("  python app.py query \"your question\"")
        console.print("  python app.py interactive\n")
        
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        return 1
    
    return 0


@cli.command()
@click.argument('query_text', metavar='QUERY')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed information')
def query(query_text: str, verbose: bool):
    """Answer a single question about the repository.
    
    QUERY: Natural language question about the httpx codebase
    
    Examples:
        python app.py query "How does httpx handle request timeouts?"
        python app.py query "What authentication methods are supported?"
        python app.py query "How is SSL validation implemented?" --verbose
    """
    try:
        console.print()
        console.print(Panel(
            f"[bold cyan]Query:[/bold cyan] {query_text}",
            title="Repo Analyst",
            border_style="cyan"
        ))
        
        # Initialize
        config = Config()
        rag = RAGPipeline(config)
        
        if verbose:
            console.print(f"\n[dim]Loaded {len(rag.chunks)} chunks from index[/dim]")
            console.print(f"[dim]Top-k retrieval: {config.get('retrieval', 'top_k')}[/dim]")
        
        console.print("\n[yellow]>> Searching repository...[/yellow]")
        
        # Query
        answer = rag.query(query_text)
        
        # Display answer
        console.print("\n" + "=" * 60)
        console.print("[bold green]Answer:[/bold green]\n")
        console.print(Markdown(answer))
        console.print("=" * 60)
        
        # Display judge score if available
        judge_score = rag.get_last_judge_score()
        if judge_score is not None:
            console.print(f"[blue]>> LLM Judge Score: {judge_score}/6[/blue]")
        
        console.print()
        
        if verbose:
            console.print(f"[dim]Conversation history: {len(rag.get_history())} turns[/dim]\n")
        
    except FileNotFoundError as e:
        console.print(f"\n[bold red]Error:[/bold red] Index not found")
        console.print("Please run indexing first:")
        console.print("  [cyan]python app.py index[/cyan]\n")
        return 1
    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}\n")
        return 1
    
    return 0


@cli.command()
@click.option('--no-history', is_flag=True, help='Disable conversation history')
def interactive(no_history: bool):
    """Start interactive query mode with conversation history.
    
    In interactive mode, you can ask multiple questions and the system
    will remember the conversation context. Previous questions and answers
    are included in the context for better follow-up questions.
    
    Commands:
        exit, quit, q - Exit interactive mode
        clear         - Clear conversation history
        history       - Show conversation history
        help          - Show available commands
    
    Example:
        python app.py interactive
    """
    console.print()
    console.print(Panel(
        "[bold cyan]Repo Analyst - Interactive Mode[/bold cyan]\n\n"
        "Ask questions about the httpx repository.\n"
        "Conversation history is maintained across queries.\n\n"
        "Type 'help' for commands, 'exit' to quit.",
        border_style="cyan"
    ))
    
    try:
        config = Config()
        
        # Disable history if requested
        if no_history:
            # Temporarily override config
            if 'conversation' not in config.config:
                config.config['conversation'] = {}
            config.config['conversation']['enable_history'] = False
            console.print("[yellow]Note: Conversation history disabled[/yellow]\n")
        
        rag = RAGPipeline(config)
        console.print(f"[green]OK[/green] Loaded {len(rag.chunks)} code chunks")
        console.print(f"[green]OK[/green] Ready for queries\n")
        
    except FileNotFoundError:
        console.print("\n[bold red]Error:[/bold red] Index not found")
        console.print("Please run indexing first:")
        console.print("  [cyan]python app.py index[/cyan]\n")
        return 1
    except Exception as e:
        console.print(f"\n[bold red]Error initializing:[/bold red] {e}")
        console.print("\nTroubleshooting:")
        console.print("  1. Make sure you've run: [cyan]python app.py index[/cyan]")
        console.print("  2. Check that your .env file contains: [cyan]open_ai_api_key[/cyan]")
        console.print("  3. Verify the httpx repository is in: [cyan]./httpx[/cyan]\n")
        return 1
    
    query_count = 0
    
    while True:
        try:
            # Prompt
            user_input = console.input("[bold cyan]You:[/bold cyan] ").strip()
            
            # Handle empty input
            if not user_input:
                continue
            
            # Handle commands
            if user_input.lower() in ['exit', 'quit', 'q']:
                console.print("\n[cyan]Goodbye![/cyan]\n")
                break
            
            elif user_input.lower() == 'clear':
                rag.clear_history()
                console.print("[green]OK: Conversation history cleared[/green]\n")
                continue
            
            elif user_input.lower() == 'history':
                history = rag.get_history()
                if not history:
                    console.print("[yellow]No conversation history yet[/yellow]\n")
                else:
                    table = Table(title="Conversation History", show_header=True)
                    table.add_column("#", style="cyan", width=4)
                    table.add_column("Query", style="white")
                    table.add_column("Answer Preview", style="dim")
                    
                    for i, turn in enumerate(history, 1):
                        answer_preview = turn['answer'][:100] + "..." if len(turn['answer']) > 100 else turn['answer']
                        table.add_row(str(i), turn['query'], answer_preview)
                    
                    console.print()
                    console.print(table)
                    console.print()
                continue
            
            elif user_input.lower() == 'help':
                console.print()
                console.print("[bold]Available Commands:[/bold]")
                console.print("  [cyan]exit, quit, q[/cyan] - Exit interactive mode")
                console.print("  [cyan]clear[/cyan]         - Clear conversation history")
                console.print("  [cyan]history[/cyan]       - Show conversation history")
                console.print("  [cyan]help[/cyan]          - Show this help message")
                console.print()
                continue
            
            # Process query
            query_count += 1
            console.print(f"\n[yellow]>> Searching... (Query #{query_count})[/yellow]\n")
            
            answer = rag.query(user_input)
            
            # Display answer
            console.print("[bold green]Answer:[/bold green]")
            console.print(Markdown(answer))
            
            # Display judge score if available
            judge_score = rag.get_last_judge_score()
            if judge_score is not None:
                console.print(f"\n[blue]>> LLM Judge Score: {judge_score}/6[/blue]")
            
            # Show history indicator
            history_len = len(rag.get_history())
            if history_len > 0:
                console.print(f"[dim]>> Conversation history: {history_len} turns[/dim]")
            
            console.print()
            
        except KeyboardInterrupt:
            console.print("\n\n[cyan]Goodbye![/cyan]\n")
            break
        except Exception as e:
            console.print(f"\n[bold red]Error:[/bold red] {e}\n")
    
    return 0


@cli.command()
def info():
    """Show system information and configuration.
    
    Displays current configuration, index statistics, and system status.
    """
    try:
        console.print()
        console.print(Panel("[bold cyan]Repo Analyst - System Information[/bold cyan]", border_style="cyan"))
        
        # Load config
        config = Config()
        
        # Configuration table
        config_table = Table(title="Configuration", show_header=True)
        config_table.add_column("Setting", style="cyan")
        config_table.add_column("Value", style="white")
        
        config_table.add_row("Repository", config.get('repository', 'path'))
        config_table.add_row("Embedding Model", config.get('vector_store', 'embedding_model'))
        config_table.add_row("LLM Model", config.get('llm', 'model'))
        config_table.add_row("Temperature", str(config.get('llm', 'temperature')))
        config_table.add_row("Top-k Retrieval", str(config.get('retrieval', 'top_k')))
        config_table.add_row("Min Score Threshold", str(config.get('retrieval', 'min_score', default='N/A')))
        config_table.add_row("Conversation History", str(config.get('conversation', 'enable_history', default=True)))
        config_table.add_row("Max History Turns", str(config.get('conversation', 'max_history_turns', default=5)))
        
        console.print()
        console.print(config_table)
        
        # Try to load index stats
        try:
            from pathlib import Path
            import faiss
            
            index_path = Path(config.get('vector_store', 'index_path'))
            metadata_path = Path(config.get('vector_store', 'metadata_path'))
            
            stats_table = Table(title="Index Statistics", show_header=True)
            stats_table.add_column("Metric", style="cyan")
            stats_table.add_column("Value", style="white")
            
            if index_path.exists():
                index = faiss.read_index(str(index_path))
                stats_table.add_row("Index Status", "[green]OK - Available[/green]")
                stats_table.add_row("Total Vectors", str(index.ntotal))
                stats_table.add_row("Vector Dimension", str(index.d))
                stats_table.add_row("Index Size", f"{index_path.stat().st_size / 1024:.2f} KB")
            else:
                stats_table.add_row("Index Status", "[red]ERROR - Not found[/red]")
            
            if metadata_path.exists():
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    chunk_count = sum(1 for _ in f)
                stats_table.add_row("Metadata Status", "[green]OK - Available[/green]")
                stats_table.add_row("Total Chunks", str(chunk_count))
                stats_table.add_row("Metadata Size", f"{metadata_path.stat().st_size / 1024:.2f} KB")
            else:
                stats_table.add_row("Metadata Status", "[red]ERROR - Not found[/red]")
            
            console.print()
            console.print(stats_table)
            
        except Exception as e:
            console.print(f"\n[yellow]Could not load index statistics: {e}[/yellow]")
        
        console.print()
        
    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}\n")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(cli())

