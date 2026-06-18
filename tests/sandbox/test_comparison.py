from sandbox.runstore import Run, TargetResult
from sandbox.comparison import build_comparison, to_markdown


def _run(rid, model, t5_conf, t5_t, cost):
    return Run(
        run_id=rid, model_code=model, model_reason=model, provider="x",
        targets=[TargetResult("kyber512_leak5", located=True, confirmed=t5_conf,
                              t_stat=t5_t, cycles=2, wall_seconds=10.0,
                              autonomous=True, verdict="PROMOTED" if t5_conf else "INVALIDATED")],
        started_at=0.0, ended_at=10.0, tokens={"prompt": 100, "completion": 50},
        cost_usd=cost, cost_estimated=True, fp_rate=0.0, notes="")


def test_build_comparison_axes():
    runs = [_run("a", "codellama:7b", True, 141.0, 0.0),
            _run("b", "gpt-4o", True, 150.0, 0.02)]
    comp = build_comparison(runs)
    assert comp["models"] == ["codellama:7b", "gpt-4o"]
    cell = comp["detection"]["kyber512_leak5"]
    assert cell[0]["confirmed"] is True and cell[1]["t_stat"] == 150.0
    assert comp["efficiency"]["cost_usd"] == [0.0, 0.02]


def test_to_markdown_contains_models_and_targets():
    runs = [_run("a", "codellama:7b", True, 141.0, 0.0)]
    md = to_markdown(build_comparison(runs))
    assert "codellama:7b" in md
    assert "kyber512_leak5" in md
