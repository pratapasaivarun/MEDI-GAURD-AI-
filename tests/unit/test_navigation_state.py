from mediguard.ui.navigation import prepare_navigation, queue_page


def test_programmatic_navigation_survives_sidebar_radio_state_on_next_run():
    session = {"workspace_navigation": "Register claim", "page": "Register claim"}

    queue_page(session, "Claim review")
    prepare_navigation(session, ["Dashboard", "Register claim", "Claim review"])

    assert session["page"] == "Claim review"
    assert session["workspace_navigation"] == "Claim review"
    assert "pending_navigation" not in session


def test_unknown_queued_page_does_not_corrupt_sidebar_navigation():
    session = {"workspace_navigation": "Dashboard"}
    queue_page(session, "Unavailable page")

    prepare_navigation(session, ["Dashboard", "Claim review"])

    assert session["workspace_navigation"] == "Dashboard"
    assert "pending_navigation" not in session
