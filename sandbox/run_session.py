import time
import uuid
from pathlib import Path

from sandbox import config
from sandbox.meter import Meter
from sandbox.gateway.router import Router
from sandbox.gateway.server import Gateway
from sandbox.runstore import Run, TargetResult, save_run
from viz.sources.state_file import load_loop_state
from viz.sources.live import LiveSource
from viz.events import RunState, StageEvent, fold_event
from viz.orchestrator import invoke_oracle

REPO_ROOT = Path(__file__).resolve().parent.parent
FINDINGS = REPO_ROOT / "shared" / "findings"
# The engine always writes its run state here (track-b-engine/engine/adversary_loop.py).
LOOP_STATE = FINDINGS / "loop_state.json"

GROUND_TRUTH = {
    "kyber512_leak2": {"category": "secret_dependent_branch", "location": "poly_tomsg"},
    "kyber512_leak4": {"category": "secret_dependent_branch", "location": "indcpa_dec"},
    "kyber512_leak5": {"category": "nonconstant_comparison", "location": "crypto_kem_dec"},
    "mldsa44_leak1": {"category": "nonconstant_comparison", "location": "mld_sign_verify_internal"},
}


class RunSession:
    """Runs one model across one target via the engine subprocess behind the gateway,
    folds live events for the UI, and writes a Run artifact at the end."""

    def __init__(self, model: str, target_id: str, target_c: Path, on_state,
                 static_scan: bool = True):
        self._model = model
        self._target_id = target_id
        self._target_c = Path(target_c)
        self._on_state = on_state
        self._static_scan = static_scan  # False = autonomous mode (no static-scan directive)
        self._run_id = uuid.uuid4().hex[:8]
        self._meter = Meter(model=model)
        keys = {p: config.api_key(p) for p in ("anthropic", "openai")}
        self._router = Router(keys={k: v for k, v in keys.items() if v})
        self._gateway = Gateway(self._router, self._meter)

    def run(self) -> Run:
        self._gateway.start()
        env = {
            "RAYQ_OLLAMA_URL": self._gateway.url,
            "RAYQ_CODE_MODEL": self._model,
            "RAYQ_REASON_MODEL": self._model,
            "RAYQ_STATIC_SCAN": "1" if self._static_scan else "0",
        }
        started = time.time()
        state = RunState(run_id=self._run_id, model_label=f"{self._model} (live)")

        # Immediate feedback: light up the target in READ before the (slow) first LLM
        # call returns, so the console leaves Idle the moment the run starts.
        fold_event(state, StageEvent(
            run_id=self._run_id, target_id=self._target_id, hyp_id="H000",
            stage="ingest", status="active", ts=time.time(),
            data={"hypothesis_text": f"{self._model} loading + reading the target source…"}))
        self._on_state(state.to_dict())

        # When the engine reaches the oracle WAIT stage, run the target's harness to
        # produce the timing feedback JSON the engine polls for. Without this the run
        # stalls at WAIT (the engine never receives feedback).
        def on_wait(hyp_id: str):
            invoke_oracle(self._target_id, hyp_id)

        source = LiveSource(self._target_c, cycles=3, on_wait_for_oracle=on_wait,
                            env_overrides=env)
        for event in source.start():
            if not event.target_id:
                event.target_id = self._target_id
            fold_event(state, event)
            self._on_state(state.to_dict())
        ended = time.time()
        self._gateway.stop()

        result = self._collect_target_result(started, ended)
        run = Run(
            run_id=self._run_id, model_code=self._model, model_reason=self._model,
            provider=config.provider_for(self._model), targets=[result],
            started_at=started, ended_at=ended,
            tokens=self._meter.totals()["tokens"],
            cost_usd=self._meter.totals()["cost_usd"],
            cost_estimated=self._meter.totals()["cost_estimated"],
            fp_rate=self._fp_rate([result]), notes="",
        )
        save_run(run)
        return run

    def _collect_target_result(self, started, ended) -> TargetResult:
        """Derive located/confirmed from the loop_state the engine wrote for this run."""
        located = confirmed = autonomous = False
        t_stat = None
        verdict = "UNKNOWN"
        cycles = 0
        if LOOP_STATE.exists():
            data = load_loop_state(LOOP_STATE)
            cycles = data.get("current_cycle", 0)
            hyps = data.get("hypotheses", [])
            if hyps:
                best = max(hyps, key=lambda h: abs(h.get("t_statistic") or 0.0))
                gt = GROUND_TRUTH.get(self._target_id, {})
                cat = best.get("category", "")
                loc = best.get("location", "")
                located = (cat == gt.get("category")) and (gt.get("location", "") in loc)
                confirmed = bool(best.get("significant"))
                t_stat = best.get("t_statistic")
                verdict = best.get("status", "UNKNOWN")
                autonomous = "MANDATORY" not in (best.get("evidence", "") or "").upper()
        return TargetResult(
            target_id=self._target_id, located=located, confirmed=confirmed,
            t_stat=t_stat, cycles=cycles, wall_seconds=round(ended - started, 1),
            autonomous=autonomous, verdict=verdict)

    @staticmethod
    def _fp_rate(results) -> float:
        promoted = [r for r in results if r.verdict == "PROMOTED"]
        if not promoted:
            return 0.0
        wrong = [r for r in promoted if not r.located]
        return round(len(wrong) / len(promoted), 3)
