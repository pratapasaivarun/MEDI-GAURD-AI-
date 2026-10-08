from ui.styles import APP_CSS


def test_stylesheet_is_a_single_well_formed_style_block():
    assert APP_CSS.startswith("<style>")
    assert APP_CSS.endswith("</style>")
    assert APP_CSS.count("<style>") == 1
    assert APP_CSS.count("</style>") == 1
