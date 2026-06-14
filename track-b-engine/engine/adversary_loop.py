#!/usr/bin/env python3
"""
adversary_loop.py — Track B Phase B3: the full multi-turn LLM adversary loop.

Cycle:
  INGEST  (codellama:7b)  -> ranked hypotheses (via ingestion.CodeIngester)
  for each hypothesis:
    VECTORIZE     (codellama:7b)  -> compilable C timing test  -> shared/vectors/
    WAIT FEEDBACK (mock or live)  -> timing JSON               -> shared/feedback/
    REFINE        (qwen3:8b)      -> PROMOTED/DEMOTED/INVALIDATED/UNCHANGED
    LOG           -> EXPERIMENT_LOG.md
    SAVE STATE    -> shared/findings/loop_state.json

All LLM calls: stream=false, temperature=0.2.
This module is driven by track-b-engine/main.py.
"""

import json
import re
import subprocess
import sys
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

# --- Paths -------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
INGESTION_DIR = REPO_ROOT / "track-b-engine" / "ingestion"
PROMPTS_DIR = REPO_ROOT / "track-b-engine" / "prompts"
ENGINE_DIR = REPO_ROOT / "track-b-engine" / "engine"
VECTORS_DIR = REPO_ROOT / "shared" / "vectors"
FEEDBACK_DIR = REPO_ROOT / "shared" / "feedback"
FINDINGS_DIR = REPO_ROOT / "shared" / "findings"
LOOP_STATE_FILE = FINDINGS_DIR / "loop_state.json"
EXPERIMENT_LOG = REPO_ROOT / "EXPERIMENT_LOG.md"
MOCK_FEEDBACK = ENGINE_DIR / "mock_feedback.py"

STAGE2_PROMPT = PROMPTS_DIR / "stage2_feedback.txt"
STAGE3_PROMPT = PROMPTS_DIR / "stage3_vector.txt"

# Make the ingestion module importable.
if str(INGESTION_DIR) not in sys.path:
    sys.path.insert(0, str(INGESTION_DIR))
from ingest import CodeIngester, Hypothesis  # noqa: E402

# --- Engine config -----------------------------------------------------------
OLLAMA_URL = "http://localhost:11434/api/chat"
CODE_MODEL = "codellama:7b"
REASON_MODEL = "qwen3:8b"
TEMPERATURE = 0.2

POLL_INTERVAL_S = 30
FEEDBACK_TIMEOUT_S = 600


# --- Helpers -----------------------------------------------------------------
def _now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def call_ollama(model: str, system: str, user: str) -> str:
    """One non-streaming chat call at temperature 0.2."""
    import requests

    payload = {
        "model": model,
        "stream": False,
        "options": {"temperature": TEMPERATURE},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    resp = requests.post(OLLAMA_URL, json=payload, timeout=300)
    resp.raise_for_status()
    return resp.json().get("message", {}).get("content", "")


def strip_think(text: str) -> str:
    """Remove <think>...</think> reasoning blocks (qwen3 emits these)."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)


def extract_json_array(text: str):
    """Parse a JSON array tolerating surrounding prose / fences / think tags."""
    text = strip_think(text).strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start, end = text.find("["), text.rfind("]")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start : end + 1])
    raise json.JSONDecodeError("no JSON array found", text, 0)


def extract_json_object(text: str):
    """Parse the first JSON object embedded in text."""
    text = strip_think(text).strip()
    start = text.find("{")
    if start == -1:
        raise json.JSONDecodeError("no JSON object found", text, 0)
    return json.JSONDecoder().raw_decode(text[start:])[0]


def extract_c_source(text: str) -> str:
    """Pull C source from a model response, dropping fences / preamble."""
    text = strip_think(text)
    text = re.sub(r"```(?:c)?", "", text)
    idx = text.find("#include")
    return text[idx:].strip() if idx != -1 else text.strip()


def looks_like_c(src: str) -> bool:
    return "#include" in src and "main" in src


# --- The loop ----------------------------------------------------------------
class AdversaryLoop:
    def __init__(self, target: str, cycles: int = 3, use_mock: bool = False,
                 resume: bool = False):
        self.target = str(Path(target))
        self.cycles = cycles
        self.use_mock = use_mock
        self.resume = resume

        self.ingester = CodeIngester()
        self.context = None
        self.sig_by_func = {}          # function name -> signature
        self.hypotheses = []           # list[Hypothesis], ranked
        self.state = {}                # per-id enriched record
        self.completed_ids = []
        self.promoted_ids = []
        self.demoted_ids = []
        self.invalidated_ids = []

        for d in (VECTORS_DIR, FEEDBACK_DIR, FINDINGS_DIR):
            d.mkdir(parents=True, exist_ok=True)

    # -- INGEST ---------------------------------------------------------------
    def ingest(self):
        self.context = self.ingester.preprocess(self.target)
        for f in self.context["functions"]:
            # location strings look like "check_key() line 4" -> key on name
            self.sig_by_func[f.name] = f.signature
        self.hypotheses = self.ingester.analyze(self.context)
        return self.hypotheses

    def _signature_for(self, hyp: Hypothesis) -> str:
        m = re.match(r"\s*([A-Za-z_]\w*)", hyp.location or "")
        if m and m.group(1) in self.sig_by_func:
            return self.sig_by_func[m.group(1)]
        # Fall back to any flagged function signature, else a generic stub.
        if self.context and self.context["flagged_functions"]:
            return self.context["flagged_functions"][0].signature
        return "int target_function(unsigned char *secret)"

    # -- VECTORIZE ------------------------------------------------------------
    def vectorize(self, hyp: Hypothesis) -> str:
        prompt = STAGE3_PROMPT.read_text()
        hyp_json = json.dumps(asdict(hyp))
        sig = self._signature_for(hyp)
        system = (
            prompt.replace("{hypothesis_json}", hyp_json)
            .replace("{function_signature}", sig)
        )
        user = (
            f"Generate the C timing test for hypothesis {hyp.id}.\n"
            f"Hypothesis JSON: {hyp_json}\n"
            f"Function signature: {sig}"
        )

        raw = call_ollama(CODE_MODEL, system, user)
        src = extract_c_source(raw)
        if not looks_like_c(src):
            # retry once with a sterner instruction
            retry_system = system + (
                "\n\nYour previous response was invalid. "
                "Return ONLY C source code starting with #include"
            )
            raw = call_ollama(CODE_MODEL, retry_system, user)
            src = extract_c_source(raw)

        out = VECTORS_DIR / f"vec_{hyp.id}_{_ts()}.c"
        out.write_text(src)
        return str(out)

    # -- WAIT FOR FEEDBACK ----------------------------------------------------
    def wait_for_feedback(self, hyp: Hypothesis):
        if self.use_mock:
            return self._mock_feedback(hyp)
        return self._poll_feedback(hyp)

    def _mock_feedback(self, hyp: Hypothesis):
        proc = subprocess.run(
            [sys.executable, str(MOCK_FEEDBACK), hyp.id],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"mock_feedback.py failed: {proc.stderr}")
        try:
            return extract_json_object(proc.stdout)
        except json.JSONDecodeError:
            # fall back to newest mock file
            files = sorted(FEEDBACK_DIR.glob("mock_timing_*.json"),
                           key=lambda p: p.stat().st_mtime)
            return json.loads(files[-1].read_text()) if files else None

    def _poll_feedback(self, hyp: Hypothesis):
        deadline = time.time() + FEEDBACK_TIMEOUT_S
        while time.time() < deadline:
            matches = [
                p for p in FEEDBACK_DIR.glob("*.json")
                if hyp.id in p.name
            ]
            if matches:
                newest = max(matches, key=lambda p: p.stat().st_mtime)
                return json.loads(newest.read_text())
            print(f"    ...waiting for feedback file containing '{hyp.id}' "
                  f"in {FEEDBACK_DIR} (poll every {POLL_INTERVAL_S}s)")
            time.sleep(POLL_INTERVAL_S)
        print(f"    WARNING: feedback timeout ({FEEDBACK_TIMEOUT_S}s) for "
              f"{hyp.id}; skipping to next hypothesis.")
        return None

    # -- REFINE ---------------------------------------------------------------
    def refine(self, hyp: Hypothesis, timing: dict) -> dict:
        prompt = STAGE2_PROMPT.read_text()
        hyps_json = json.dumps([asdict(hyp)])
        timing_json = json.dumps(timing)
        run_count = str(timing.get("run_count", ""))
        system = (
            prompt.replace("{hypotheses_json}", hyps_json)
            .replace("{timing_json}", timing_json)
            .replace("{run_count}", run_count)
        )
        user = (
            f"Hypotheses: {hyps_json}\n"
            f"Timing data: {timing_json}\n"
            f"Run count: {run_count}"
        )

        raw = call_ollama(REASON_MODEL, system, user)
        try:
            records = extract_json_array(raw)
        except json.JSONDecodeError:
            retry_system = system + (
                "\n\nYour previous response was not valid JSON. Return ONLY "
                "the JSON array starting with [ and ending with ]"
            )
            raw = call_ollama(REASON_MODEL, retry_system, user)
            records = extract_json_array(raw)

        # find the record matching this hypothesis id (default to first)
        rec = next((r for r in records if str(r.get("id")) == hyp.id),
                   records[0] if records else {})
        return rec

    # -- LOG ------------------------------------------------------------------
    def log_cycle(self, cycle: int, hyp: Hypothesis, status: str,
                  timing: dict, next_hint: str):
        t_stat = timing.get("t_statistic", "n/a") if timing else "n/a"
        sig = timing.get("significant", "n/a") if timing else "n/a"
        line = (
            f"[{_now_iso()}] [B] Phase: B3 | Cycle: {cycle} | "
            f"Hypothesis: {hyp.id} | Status: {status} | "
            f"t_stat: {t_stat} | significant: {sig} | "
            f"Next: {next_hint}\n"
        )
        with EXPERIMENT_LOG.open("a") as fh:
            fh.write(line)

    # -- SAVE STATE -----------------------------------------------------------
    def save_state(self, cycle: int):
        payload = {
            "target_file": self.target,
            "current_cycle": cycle,
            "total_cycles": self.cycles,
            "hypotheses": list(self.state.values()),
            "last_updated": datetime.now().isoformat(),
            "completed_ids": self.completed_ids,
            "promoted_ids": self.promoted_ids,
            "demoted_ids": self.demoted_ids,
            "invalidated_ids": self.invalidated_ids,
        }
        LOOP_STATE_FILE.write_text(json.dumps(payload, indent=2))

    def _load_resume(self):
        if self.resume and LOOP_STATE_FILE.exists():
            prev = json.loads(LOOP_STATE_FILE.read_text())
            self.completed_ids = prev.get("completed_ids", [])
            self.promoted_ids = prev.get("promoted_ids", [])
            self.demoted_ids = prev.get("demoted_ids", [])
            self.invalidated_ids = prev.get("invalidated_ids", [])
            for rec in prev.get("hypotheses", []):
                self.state[rec["id"]] = rec
            print(f"Resuming: {len(self.completed_ids)} hypothesis(es) already "
                  f"completed: {self.completed_ids}")

    # -- RUN ------------------------------------------------------------------
    def run(self):
        self._load_resume()
        self.ingest()

        # seed state with any not-yet-seen hypotheses
        for h in self.hypotheses:
            self.state.setdefault(h.id, {**asdict(h), "status": "PENDING"})

        cycle = 0
        for hyp in self.hypotheses:
            if cycle >= self.cycles:
                break
            if hyp.id in self.completed_ids:
                continue
            cycle += 1

            # VECTORIZE
            vec_path = self.vectorize(hyp)

            # WAIT FOR FEEDBACK
            timing = self.wait_for_feedback(hyp)

            if timing is None:
                status, next_hint, evidence = "UNCHANGED", "Re-run; no feedback received.", ""
                rev_conf, exploit = hyp.confidence, None
            else:
                rec = self.refine(hyp, timing)
                status = str(rec.get("status", "UNCHANGED")).upper()
                next_hint = rec.get("next_test_hint", "")
                evidence = rec.get("evidence", "")
                rev_conf = rec.get("revised_confidence", hyp.confidence)
                exploit = rec.get("exploitation_path")

            # update in-memory record / rankings
            t_stat = timing.get("t_statistic") if timing else None
            significant = timing.get("significant") if timing else None
            self.state[hyp.id] = {
                **asdict(hyp),
                "status": status,
                "revised_confidence": rev_conf,
                "evidence": evidence,
                "next_test_hint": next_hint,
                "t_statistic": t_stat,
                "significant": significant,
                "vector_file": vec_path,
                "feedback": timing,
                "exploitation_path": exploit,
            }

            if hyp.id not in self.completed_ids:
                self.completed_ids.append(hyp.id)
            for bucket, name in (
                (self.promoted_ids, "PROMOTED"),
                (self.demoted_ids, "DEMOTED"),
                (self.invalidated_ids, "INVALIDATED"),
            ):
                if status == name and hyp.id not in bucket:
                    bucket.append(hyp.id)

            # LOG + SAVE STATE
            self.log_cycle(cycle, hyp, status, timing, next_hint)
            self.save_state(cycle)

            # console line
            t_disp = f"{t_stat:.3f}" if isinstance(t_stat, (int, float)) else "n/a"
            print(f"[Cycle {cycle}] Hypothesis {hyp.id} → {status} "
                  f"(t={t_disp}, sig={significant})")

            # stop early if everything seen so far is invalidated
            if (self.completed_ids and
                    all(self.state[i]["status"] == "INVALIDATED"
                        for i in self.completed_ids)):
                print("All processed hypotheses INVALIDATED — stopping early.")
                break

        return self.state
