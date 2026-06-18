from sandbox.runstore import Run, TargetResult, save_run, load_run, list_runs


def _sample_run():
    return Run(
        run_id="r1", model_code="gpt-4o", model_reason="gpt-4o", provider="openai",
        targets=[
            TargetResult("kyber512_leak5", located=True, confirmed=True, t_stat=141.0,
                         cycles=2, wall_seconds=12.3, autonomous=True, verdict="PROMOTED"),
            TargetResult("kyber512_leak2", located=True, confirmed=False, t_stat=-0.17,
                         cycles=3, wall_seconds=20.1, autonomous=True, verdict="INVALIDATED"),
        ],
        started_at=1000.0, ended_at=1100.0,
        tokens={"prompt": 5000, "completion": 1200}, cost_usd=0.05,
        cost_estimated=True, fp_rate=0.0, notes="",
    )


def test_round_trip(tmp_path):
    run = _sample_run()
    path = save_run(run, runs_dir=tmp_path)
    assert path.exists()
    loaded = load_run(path)
    assert loaded.run_id == "r1"
    assert loaded.targets[0].t_stat == 141.0
    assert loaded.targets[1].confirmed is False
    assert loaded.cost_usd == 0.05


def test_list_runs_sorted(tmp_path):
    a = _sample_run(); a.run_id = "aaa"
    b = _sample_run(); b.run_id = "bbb"
    save_run(a, runs_dir=tmp_path)
    save_run(b, runs_dir=tmp_path)
    ids = [r.run_id for r in list_runs(runs_dir=tmp_path)]
    assert ids == ["aaa", "bbb"]


def test_artifact_has_no_key_fields(tmp_path):
    import json
    path = save_run(_sample_run(), runs_dir=tmp_path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert "api_key" not in raw and "key" not in raw
