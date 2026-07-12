from pathlib import Path

STYLE_DIR = Path(__file__).resolve().parents[2] / "docs" / "style"


def test_tokens_css_defines_required_primitives():
    css = (STYLE_DIR / "tokens.css").read_text(encoding="utf-8")
    for var in [
        "--color-paper", "--color-surface", "--color-border",
        "--color-ink-soft", "--color-ink",
        "--color-blue", "--color-green", "--color-orange", "--color-red",
        "--font-sans", "--font-mono",
        "--radius-outer", "--radius-mid", "--radius-inner",
        "--stroke",
    ]:
        assert var in css, f"tokens.css missing {var}"


def test_tokens_css_hex_values_match_spec():
    css = (STYLE_DIR / "tokens.css").read_text(encoding="utf-8")
    for hex_value in [
        "#F9F8F3", "#E2E1DA", "#BEBEBE", "#313131", "#262626",
        "#0099FF", "#2FBB45", "#DC762D", "#FB2C55",
    ]:
        assert hex_value in css, f"tokens.css missing {hex_value}"
    assert "#979797" not in css, "grey 2 (#979797) must not appear -- explicitly dropped"


def test_subsystem_academic_consumes_tokens_not_hardcoded_hex():
    css = (STYLE_DIR / "subsystem-academic.css").read_text(encoding="utf-8")
    assert "@import" in css and "tokens.css" in css
    assert ".callout" in css
    assert ".pill" in css
    assert "var(--radius-mid)" in css
    assert "var(--radius-inner)" in css
    # subsystem file should not invent its own hex colors
    import re
    hex_literals = re.findall(r"#[0-9A-Fa-f]{6}\b", css)
    assert hex_literals == [], f"subsystem-academic.css must only use var(--color-*), found: {hex_literals}"
