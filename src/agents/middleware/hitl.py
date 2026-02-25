"""
HumanInTheLoopMiddleware — manages the pause-and-review step.

In CLI mode  : prompts the staff reviewer in the terminal.
In API mode  : stores the pending draft in state; the web UI calls
               POST /api/hitl/respond to inject the review decision.
"""
from __future__ import annotations
import sys


class HumanInTheLoopMiddleware:
    """
    Handles the HITL interaction surface. Supports two modes:

    cli  — blocking stdin prompt (for CLI end-to-end runs)
    api  — non-blocking; the caller is expected to provide the review
           result via an external mechanism (e.g., HTTP endpoint).
    """

    def review_cli(self, draft: str) -> tuple[str, str]:
        """
        Presents the draft to a human reviewer in the terminal.

        Returns (action, final_response) where action ∈ {approved, edited, escalated}.
        """
        print("\n" + "═" * 60)
        print("  ⚑  HUMAN-IN-THE-LOOP REVIEW")
        print("═" * 60)
        print(f"\nDraft response:\n\n{draft}\n")
        print("Options:")
        print("  [A] Approve — send as-is")
        print("  [E] Edit    — provide a revised response")
        print("  [X] Escalate to senior staff")
        print()

        while True:
            choice = input("Your choice (A/E/X): ").strip().upper()
            if choice == "A":
                return "approved", draft
            elif choice == "E":
                print("Enter your revised response (end with a blank line):")
                lines = []
                while True:
                    line = input()
                    if line == "":
                        break
                    lines.append(line)
                edited = "\n".join(lines).strip() or draft
                return "edited", edited
            elif choice == "X":
                return "escalated", (
                    "This request has been escalated to our senior patient-care team. "
                    "A staff member will contact you within 2 business hours."
                )
            else:
                print("Please enter A, E, or X.")

    def review_api(self, draft: str, action: str, edited_text: str | None = None) -> tuple[str, str]:
        """
        Non-blocking path used by the FastAPI server.
        action ∈ {approved, edited, escalated}
        """
        if action == "approved":
            return "approved", draft
        elif action == "edited" and edited_text:
            return "edited", edited_text.strip()
        elif action == "escalated":
            return "escalated", (
                "This request has been escalated to our senior patient-care team. "
                "A staff member will contact you within 2 business hours."
            )
        else:
            return "approved", draft
