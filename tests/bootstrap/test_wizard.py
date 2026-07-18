from bootstrap.wizard import GREEN, INK_SOFT, RED, _stage_for_line, _style_line, _style_verdict


def test_stage_for_line_detects_ingest():
    assert _stage_for_line("No secret-handling functions flagged; analyzing full source.") == "INGEST"


def test_stage_for_line_detects_oracle_waiting():
    assert _stage_for_line("    ...waiting for feedback file timing_H001_*.json in /app/shared/feedback (poll every 30s)") == "ORACLE"


def test_stage_for_line_detects_oracle_running():
    assert _stage_for_line(">>> detected hypothesis id: H001 — running oracle from kyber512_leak1") == "ORACLE"


def test_stage_for_line_detects_refine():
    assert _stage_for_line("[Cycle 1] Hypothesis H001 → PROMOTED (t=-1488.839, sig=True)") == "REFINE"


def test_stage_for_line_detects_done():
    assert _stage_for_line("=== LOOP COMPLETE ===") == "DONE"


def test_stage_for_line_returns_none_for_unrecognized_text():
    assert _stage_for_line("some unrelated line of output") is None


def test_style_line_highlights_promoted_green_bold():
    result = _style_line("[Cycle 1] Hypothesis H001 → PROMOTED (t=-1488.839, sig=True)")
    assert result.startswith(f"[bold {GREEN}]")
    assert result.endswith("[/]")


def test_style_line_highlights_demoted_red():
    result = _style_line("[Cycle 1] Hypothesis H002 → DEMOTED (t=0.4, sig=False)")
    assert result.startswith(f"[{RED}]")


def test_style_line_highlights_invalidated_red():
    result = _style_line("[Cycle 1] Hypothesis H003 → INVALIDATED")
    assert result.startswith(f"[{RED}]")


def test_style_line_highlights_warning():
    result = _style_line(">>> WARNING: no hypothesis id detected (loop produced no hypotheses?)")
    assert result.startswith(f"[bold {RED}]")


def test_style_line_dims_waiting_lines():
    result = _style_line("    ...waiting for feedback file timing_H001_*.json in /app/shared/feedback (poll every 30s)")
    assert result.startswith(f"[dim {INK_SOFT}]")


def test_style_line_escapes_text_that_looks_like_markup():
    # If engine output ever contains a substring that looks like a valid
    # rich style tag (e.g. "[red]" as literal text, not markup we intended),
    # it must come out escaped so rich doesn't try to interpret it.
    result = _style_line("some line mentioning [red] as literal text")
    assert "\\[red]" in result


def test_style_line_falls_back_unstyled_for_unrecognized_text():
    result = _style_line("plain line with nothing special")
    assert result == "plain line with nothing special"


def test_style_verdict_uses_green_for_promoted():
    assert _style_verdict("PROMOTED") == f"[bold {GREEN}]PROMOTED[/]"


def test_style_verdict_uses_red_for_demoted():
    assert _style_verdict("DEMOTED") == f"[bold {RED}]DEMOTED[/]"


def test_style_verdict_uses_red_for_invalidated():
    assert _style_verdict("INVALIDATED") == f"[bold {RED}]INVALIDATED[/]"


def test_style_verdict_leaves_unknown_verdicts_unstyled():
    assert _style_verdict("NO RESULT") == "NO RESULT"
