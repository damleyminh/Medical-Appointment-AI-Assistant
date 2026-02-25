#!/usr/bin/env python3
"""
cli.py — Command-line entry point for the Appointment Assistance System.

Usage:
    python cli.py
    python cli.py --message "I need to reschedule my MRI appointment"
    python cli.py --message "What do I need to do to prepare for a CT scan?"
    python cli.py --demo
"""
from __future__ import annotations

import json
import sys
import os
import argparse
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

load_dotenv()

console = Console()

DEMO_SCENARIOS = [
    {
        "label": "Reschedule",
        "message": "Hi, I need to reschedule my appointment. I have a conflict on the current date.",
    },
    {
        "label": "Cancel",
        "message": "I'd like to cancel my upcoming appointment please.",
    },
    {
        "label": "Prep Instructions (MRI)",
        "message": "Can you tell me how to prepare for my MRI scan?",
    },
    {
        "label": "Emergency (Escalation)",
        "message": "I am having severe chest pain and difficulty breathing right now.",
    },
    {
        "label": "Unknown / Need Info",
        "message": "What time does the front desk open?",
    },
]


def _check_env() -> bool:
    if not os.getenv("OPENAI_API_KEY"):
        console.print(
            Panel(
                "[bold red]OPENAI_API_KEY not set.[/bold red]\n\n"
                "Create a [bold].env[/bold] file from [bold].env.example[/bold] "
                "and add your OpenAI API key.",
                title="Configuration Error",
                border_style="red",
            )
        )
        return False
    return True


def run_once(message: str, hitl_mode: str = "cli") -> dict:
    """Execute the graph for a single patient message. Returns final state."""
    from src.agents.graph import appointment_graph

    initial_state = {
        "raw_input":         message,
        "messages":          [],
        "intent":            None,
        "pii_masked_input":  None,
        "pii_map":           {},
        "moderation_flagged": False,
        "mod_categories":    [],
        "call_count":        0,
        "draft_response":    None,
        "final_response":    None,
        "hitl_action":       None,
        "status":            None,
        "route_path":        [],
        "error":             None,
        "hitl_pending":      False,
        "hitl_api_action":   None,
        "hitl_api_edit":     None,
        "run_id":            "",
        "timestamp":         "",
    }

    final_state = appointment_graph.invoke(initial_state)
    return final_state


def _print_result(state: dict) -> None:
    status = state.get("status", "UNKNOWN")
    status_color = {
        "READY":     "green",
        "NEED_INFO": "yellow",
        "ESCALATE":  "red",
    }.get(status, "white")

    console.print()
    console.print(Panel(
        f"[bold {status_color}]{status}[/bold {status_color}]",
        title="Terminal Status",
        border_style=status_color,
        width=40,
    ))

    # Execution trace table
    table = Table(title="Execution Trace", box=box.SIMPLE_HEAVY, show_lines=False)
    table.add_column("Field",  style="dim", width=22)
    table.add_column("Value",  style="bright_white")
    table.add_row("Run ID",         state.get("run_id", "—"))
    table.add_row("Timestamp",      state.get("timestamp", "—"))
    table.add_row("Intent",         state.get("intent", "—"))
    table.add_row("Route Path",     " → ".join(state.get("route_path", [])))
    table.add_row("HITL Action",    state.get("hitl_action", "—"))
    table.add_row("LLM Calls",      str(state.get("call_count", 0)))
    table.add_row("PII Detected",   "Yes" if state.get("pii_map") else "No")
    table.add_row("Mod Flagged",    "Yes" if state.get("moderation_flagged") else "No")
    if state.get("error"):
        table.add_row("[red]Error[/red]", state.get("error", ""))
    console.print(table)

    console.print(Panel(
        state.get("final_response", "No response generated."),
        title="Final Client-Facing Response",
        border_style="blue",
    ))


def main():
    parser = argparse.ArgumentParser(
        description="Appointment Assistance System — MBAN 5510 Final Project"
    )
    parser.add_argument(
        "--message", "-m", type=str,
        help="Patient message to process. If omitted, prompts interactively."
    )
    parser.add_argument(
        "--demo", action="store_true",
        help="Run all demo scenarios sequentially (non-interactive, auto-approves HITL)."
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output the final state as JSON instead of rich formatting."
    )
    args = parser.parse_args()

    if not _check_env():
        sys.exit(1)

    if args.demo:
        console.print(Panel(
            "[bold cyan]DEMO MODE[/bold cyan] — Running all scenarios with auto-approved HITL.",
            border_style="cyan",
        ))
        # Patch HITL to auto-approve for demo
        import src.middleware.hitl as hitl_module
        original_review_cli = hitl_module.HumanInTheLoopMiddleware.review_cli
        def auto_approve(self, draft):
            console.print("[dim]  [HITL] Auto-approving draft for demo...[/dim]")
            return "approved", draft
        hitl_module.HumanInTheLoopMiddleware.review_cli = auto_approve

        for scenario in DEMO_SCENARIOS:
            console.rule(f"[bold yellow]Scenario: {scenario['label']}[/bold yellow]")
            console.print(f"[dim]Input:[/dim] {scenario['message']}\n")
            try:
                state = run_once(scenario["message"])
                _print_result(state)
            except Exception as exc:
                console.print(f"[red]Error during scenario '{scenario['label']}': {exc}[/red]")
            console.print()
        return

    # Single message mode
    if args.message:
        message = args.message
    else:
        console.print(Panel(
            "[bold]Appointment Assistance System[/bold]\n"
            "Supported requests: [cyan]Reschedule[/cyan] · [cyan]Cancel[/cyan] · [cyan]Prep Instructions[/cyan]",
            border_style="blue",
        ))
        message = console.input("[bold green]Patient message:[/bold green] ").strip()
        if not message:
            console.print("[red]No message entered. Exiting.[/red]")
            sys.exit(1)

    console.print(f"\n[dim]Processing:[/dim] {message}\n")

    try:
        state = run_once(message)
    except Exception as exc:
        console.print(f"[red bold]Fatal error:[/red bold] {exc}")
        sys.exit(1)

    if args.json:
        # Exclude non-serialisable fields
        out = {k: v for k, v in state.items() if k != "messages"}
        print(json.dumps(out, indent=2, default=str))
    else:
        _print_result(state)


if __name__ == "__main__":
    main()
