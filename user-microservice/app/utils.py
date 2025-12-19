# UTILITY reusable generic functions

def normalize_email(email: str) -> str:
    """Convert email to lowercase and strip whitespace."""
    return email.strip().lower()
