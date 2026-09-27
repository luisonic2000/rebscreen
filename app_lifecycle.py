"""Small, testable policy for the main-window close button."""


def close_action() -> str:
    """Closing the main window deliberately minimizes to the tray."""
    return "tray"
