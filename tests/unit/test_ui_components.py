from mediguard.ui.components import _line_item_status_label


def test_line_item_status_labels_are_plain_text_for_supported_table_column():
    assert _line_item_status_label("covered") == "Covered"
    assert _line_item_status_label("partial") == "Partially covered"
    assert _line_item_status_label("excluded") == "Excluded"
    assert _line_item_status_label("needs_review") == "Needs review"
