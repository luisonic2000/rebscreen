from media_display import artwork_for_display, page_after_media_refresh


def test_media_refresh_never_changes_the_selected_page():
    assert page_after_media_refresh(0) == 0
    assert page_after_media_refresh(1) == 1


def test_missing_current_artwork_clears_the_previous_cover():
    previous_cover = object()
    assert artwork_for_display(previous_cover) is previous_cover
    assert artwork_for_display(None) is None
