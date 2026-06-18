import json
import time
from pathlib import Path

import webview

from .orchestrator import Orchestrator

REPO_ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = Path(__file__).resolve().parent / "web"
TARGETS_JSON = Path(__file__).resolve().parent / "targets.json"


class API:
    """Python API exposed to the JS frontend via window.pywebview.api.*"""

    def __init__(self):
        self._window = None
        self._orchestrator: Orchestrator = None

    def set_window(self, window) -> None:
        self._window = window
        self._orchestrator = Orchestrator(on_state=self._push_state)

    def _push_state(self, state_dict: dict) -> None:
        if self._window:
            payload = json.dumps(state_dict)
            self._window.evaluate_js(f"window.onStateUpdate({payload})")

    def _init_targets(self) -> None:
        targets = json.loads(TARGETS_JSON.read_text(encoding="utf-8"))
        payload = json.dumps(targets)
        self._window.evaluate_js(f"window.initTargets({payload})")

    def start_replay_all(self, step_delay: float = 0.6) -> None:
        paths = self._orchestrator.all_replay_paths()
        if not paths:
            self._push_state({"run_id": "none", "model_label": "No replay files found",
                              "targets": {}, "finished": True})
            return
        self._orchestrator.start_replay_all(paths, step_delay=step_delay)

    def stop_run(self) -> None:
        if self._orchestrator:
            self._orchestrator.stop()

    def start_live(self, target_id: str) -> None:
        """Called by JS to start a live run (A2)."""
        self._orchestrator.start_live(target_id)

    # ── Phase B: multi-LLM sandbox ──────────────────────────────────────────
    def list_models(self) -> None:
        from sandbox import config
        self._window.evaluate_js(
            f"window.onModels({json.dumps(config.model_registry())})")

    def model_available(self, model: str) -> bool:
        from sandbox import config
        provider = config.provider_for(model)
        return provider == "ollama" or config.api_key(provider) is not None

    def start_sandbox_run(self, model: str, target_id: str) -> None:
        import threading
        from sandbox.run_session import RunSession
        targets = json.loads(TARGETS_JSON.read_text(encoding="utf-8"))
        meta = next((t for t in targets if t["id"] == target_id), None)
        if not meta or not meta.get("focused_target"):
            return
        target_c = REPO_ROOT / meta["focused_target"]

        def _go():
            RunSession(model, target_id, target_c, on_state=self._push_state).run()

        threading.Thread(target=_go, daemon=True).start()

    def list_runs(self) -> None:
        from dataclasses import asdict
        from sandbox.runstore import list_runs
        runs = [asdict(r) for r in list_runs()]
        self._window.evaluate_js(f"window.onRuns({json.dumps(runs)})")

    def build_comparison(self, run_ids: list) -> None:
        import time as _time
        from sandbox.runstore import list_runs, RUNS_DIR
        from sandbox.comparison import build_comparison, to_markdown
        chosen = [r for r in list_runs() if r.run_id in run_ids]
        comp = build_comparison(chosen)
        md = to_markdown(comp)
        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        stamp = _time.strftime("%Y%m%d_%H%M%S")
        (RUNS_DIR / f"comparison_{stamp}.md").write_text(md, encoding="utf-8")
        self._window.evaluate_js(f"window.onComparison({json.dumps(comp)})")


def start_app(autostart_replay: bool = False) -> None:
    """Create the pywebview window and enter the main loop."""
    api = API()
    window = webview.create_window(
        title="Rayquaza — Pipeline Visualizer",
        url=str(WEB_DIR / "index.html"),
        js_api=api,
        width=1100,
        height=620,
        resizable=True,
        background_color="#0d1117",
    )
    api.set_window(window)

    def on_loaded():
        api._init_targets()
        api.list_models()
        if autostart_replay:
            time.sleep(0.3)
            api.start_replay_all()

    window.events.loaded += on_loaded
    webview.start(debug=False)
