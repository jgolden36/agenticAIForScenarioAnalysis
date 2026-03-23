"""Human-in-the-loop review interface (Module 5).

Provides CLI-based analyst review with approve/reject/modify actions.
The interface contract is designed so a web UI can be swapped in later
by implementing the same ReviewInterface protocol.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from src.common.logging import get_logger
from src.common.types import ValidationStatus

logger = get_logger(__name__)


class ReviewDecision:
    """Represents an analyst's review decision."""

    def __init__(
        self,
        status: ValidationStatus,
        comments: str = "",
        modifications: dict[str, Any] | None = None,
    ) -> None:
        self.status = status
        self.comments = comments
        self.modifications = modifications or {}


class ReviewInterface(ABC):
    """Abstract interface for analyst review.

    Implement this for different UIs (CLI, web, etc.).
    """

    @abstractmethod
    def present_for_review(
        self, title: str, content: str, data: Any = None
    ) -> ReviewDecision:
        """Present content to the analyst for review.

        Args:
            title: What is being reviewed (e.g., "Scenario Narratives").
            content: Formatted text to display.
            data: Optional structured data for programmatic access.

        Returns:
            The analyst's review decision.
        """

    @abstractmethod
    def present_comparison(
        self, title: str, items: list[dict[str, Any]]
    ) -> ReviewDecision:
        """Present a side-by-side comparison for review.

        Args:
            title: What is being compared.
            items: List of items to compare, each a dict with display fields.

        Returns:
            The analyst's review decision.
        """


class CLIReviewInterface(ReviewInterface):
    """CLI-based analyst review interface.

    Pauses execution and prompts the analyst for input via stdin.
    """

    def present_for_review(
        self, title: str, content: str, data: Any = None
    ) -> ReviewDecision:
        """Display content and prompt for approval."""
        print(f"\n{'='*60}")
        print(f"  ANALYST REVIEW: {title}")
        print(f"{'='*60}\n")
        print(content)
        print(f"\n{'='*60}")

        while True:
            choice = input("\n[A]pprove / [R]eject / [M]odify? ").strip().upper()
            if choice == "A":
                comments = input("Comments (optional): ").strip()
                return ReviewDecision(
                    status=ValidationStatus.APPROVED, comments=comments
                )
            elif choice == "R":
                comments = input("Reason for rejection: ").strip()
                return ReviewDecision(
                    status=ValidationStatus.REJECTED, comments=comments
                )
            elif choice == "M":
                comments = input("Describe modifications: ").strip()
                return ReviewDecision(
                    status=ValidationStatus.MODIFIED, comments=comments
                )
            else:
                print("Please enter A, R, or M.")

    def present_comparison(
        self, title: str, items: list[dict[str, Any]]
    ) -> ReviewDecision:
        """Display items side by side and prompt for approval."""
        print(f"\n{'='*60}")
        print(f"  COMPARISON: {title}")
        print(f"{'='*60}\n")

        for i, item in enumerate(items):
            print(f"--- Item {i+1} ---")
            for key, value in item.items():
                print(f"  {key}: {value}")
            print()

        return self.present_for_review(title, "(see comparison above)")


class AutoApproveReviewInterface(ReviewInterface):
    """Auto-approving review interface for testing and batch runs.

    Automatically approves everything without human input.
    """

    def present_for_review(
        self, title: str, content: str, data: Any = None
    ) -> ReviewDecision:
        logger.info(f"Auto-approving review: {title}")
        return ReviewDecision(status=ValidationStatus.APPROVED)

    def present_comparison(
        self, title: str, items: list[dict[str, Any]]
    ) -> ReviewDecision:
        logger.info(f"Auto-approving comparison: {title}")
        return ReviewDecision(status=ValidationStatus.APPROVED)
