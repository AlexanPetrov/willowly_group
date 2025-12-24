"""Utility functions for common operations across the application."""


def normalize_email(email: str) -> str:
    """Convert email to lowercase and strip whitespace."""
    return email.strip().lower()
