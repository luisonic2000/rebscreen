"""Pure rules for the media page, kept independent from Tk and WinRT."""
from __future__ import annotations


def page_after_media_refresh(current_page: int) -> int:
    """A background refresh may update content, but never navigate the user."""
    return current_page


def artwork_for_display(incoming_art: object | None) -> object | None:
    """Use only artwork from the current session; never retain stale covers."""
    return incoming_art
