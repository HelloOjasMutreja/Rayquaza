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

    def start_replay_all(self) -> None:
        paths = self._orchestrator.all_replay_paths()
        if not paths:
            self._push_state({"run_id": "none", "model_label": "No replay files found",
                              "targets": {}, "finished": True})
            return
        self._orchestrator.start_replay(paths[-1], step_delay=0.6)

    def stop_run(self) -> None:
        if self._orchestrator:
            self._orchestrator.stop()


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
        if autostart_replay:
            time.sleep(0.3)
            api.start_replay_all()

    window.events.loaded += on_loaded
    webview.start(debug=False)
