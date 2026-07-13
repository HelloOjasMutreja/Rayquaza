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


def test_subsystem_primer_consumes_tokens_not_hardcoded_hex():
    css = (STYLE_DIR / "subsystem-primer.css").read_text(encoding="utf-8")
    assert "@import" in css and "tokens.css" in css
    assert ".callout" in css
    assert ".pill" in css
    assert "var(--radius-mid)" in css
    assert "var(--radius-inner)" in css
    import re
    hex_literals = re.findall(r"#[0-9A-Fa-f]{6}\b", css)
    assert hex_literals == [], f"subsystem-primer.css must only use var(--color-*), found: {hex_literals}"


def test_subsystem_primer_uses_green_accent_and_bigger_type_than_academic():
    academic = (STYLE_DIR / "subsystem-academic.css").read_text(encoding="utf-8")
    primer = (STYLE_DIR / "subsystem-primer.css").read_text(encoding="utf-8")
    # primer's lead accent (secnum/fignum/reftag/links) is green, not blue
    assert "color: var(--color-green);" in primer
    # primer body/heading type is larger than academic's, per user direction
    import re
    academic_body_pt = float(re.search(r"body\s*\{[^}]*font-size:\s*([\d.]+)pt", academic, re.S).group(1))
    primer_body_pt = float(re.search(r"body\s*\{[^}]*font-size:\s*([\d.]+)pt", primer, re.S).group(1))
    assert primer_body_pt > academic_body_pt
