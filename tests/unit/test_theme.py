from contracting_hub import theme


def test_theme_exports_global_tokens_and_assets() -> None:
    assert theme.ACCENT_COLOR == "grass"
    assert theme.FONT_FAMILIES["display"].startswith('"Space Grotesk"')
    assert theme.COLOR_TOKENS["canvas"] == "#f5efe2"
    assert theme.SPACING_SCALE["7"] == "2rem"
    assert theme.LAYOUT_TOKENS["max_width"] == "76rem"
    assert theme.APP_STYLESHEETS
    assert theme.APP_STYLE["--hub-color-canvas"] == theme.COLOR_TOKENS["canvas"]
    assert theme.APP_STYLE["--hub-layout-max-width"] == theme.LAYOUT_TOKENS["max_width"]
    assert theme.APP_STYLE["font_family"] == "var(--hub-font-body)"
