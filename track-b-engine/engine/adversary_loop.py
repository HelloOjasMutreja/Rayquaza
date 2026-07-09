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
import os
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
OLLAMA_URL = os.environ.get("RAYQ_OLLAMA_URL", "http://localhost:11434/api/chat")
CODE_MODEL = os.environ.get("RAYQ_CODE_MODEL", "codellama:7b")
REASON_MODEL = os.environ.get("RAYQ_REASON_MODEL", "qwen3:8b")
TEMPERATURE = 0.2

POLL_INTERVAL_S = 30
FEEDBACK_TIMEOUT_S = 600


# --- Helpers -----------------------------------------------------------------
def _now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def call_ollama(model: str, system: str, user: str, fmt: str = None) -> str:
    """One non-streaming chat call at temperature 0.2.

    fmt="json" constrains the model to valid JSON (used for the refine step);
    leave it None for vectorize, whose output is C source, not JSON.
    """
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
    if fmt:
        payload["format"] = fmt
    resp = requests.post(OLLAMA_URL, json=payload, timeout=300)
    resp.raise_for_status()
    return resp.json().get("message", {}).get("content", "")


def strip_think(text: str) -> str:
    """Remove <think>...</think> reasoning blocks (qwen3 emits these)."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)


def _normalize_to_list(obj):
    """Coerce a parsed JSON value into a list of record dicts (format:json may
    return a bare object, a single record, or a {"results": [...]} wrapper)."""
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        for v in obj.values():
            if isinstance(v, list):
                return v
        return [obj]
    return []


def extract_json_array(text: str):
    """Parse a JSON array tolerating surrounding prose / fences / think tags / dict."""
    text = strip_think(text).strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return _normalize_to_list(json.loads(text))
    except json.JSONDecodeError:
        pass
    start, end = text.find("["), text.rfind("]")
    if start != -1 and end != -1 and end > start:
        return _normalize_to_list(json.loads(text[start : end + 1]))
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


def _parse_c_params(sig: str) -> list:
    """Parse parameter list from a C function signature into a list of dicts."""
    m = re.search(r'\(([^)]*)\)', sig)
    if not m:
        return []
    params_str = m.group(1).strip()
    if not params_str or params_str == 'void':
        return []
    params = []
    for raw in params_str.split(','):
        raw = raw.strip()
        if not raw:
            continue
        cleaned = re.sub(r'\b(?:const|static|restrict|volatile)\b', '', raw).strip()
        arr_m = re.search(r'\[(\d+)\]', cleaned)
        is_array = bool(arr_m)
        array_size = int(arr_m.group(1)) if arr_m else None
        if is_array:
            cleaned = re.sub(r'\[\d+\]', '', cleaned).strip()
        is_ptr = '*' in cleaned
        cleaned = cleaned.replace('*', '').strip()
        parts = cleaned.split()
        if len(parts) >= 2:
            name, base_type = parts[-1], ' '.join(parts[:-1])
        elif len(parts) == 1:
            name, base_type = parts[0], 'int'
        else:
            continue
        params.append({'type': base_type, 'name': name,
                       'is_ptr': is_ptr, 'is_array': is_array, 'array_size': array_size})
    return params


# Template for the deterministic fallback harness (used when LLM output won't compile).
# All placeholders are ALL_CAPS tokens replaced via str.replace(), not Python format().
_FALLBACK_TMPL = r"""#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <stdint.h>
#include <math.h>

/* fallback: LLM vector did not compile; harness generated from hypothesis metadata */

STUB_SIG {
    /* stub */
}

#define N_REPS 10000

int main(void) {
    struct timespec t0, t1;
    double ns_A[N_REPS], ns_B[N_REPS];
DECLS
    int i;

    for (i = 0; i < N_REPS; i++) {
INIT_A
        clock_gettime(CLOCK_MONOTONIC, &t0);
        CALL_A;
        clock_gettime(CLOCK_MONOTONIC, &t1);
        ns_A[i] = (double)(t1.tv_sec - t0.tv_sec) * 1e9
                + (double)(t1.tv_nsec - t0.tv_nsec);
    }
    for (i = 0; i < N_REPS; i++) {
INIT_B
        clock_gettime(CLOCK_MONOTONIC, &t0);
        CALL_B;
        clock_gettime(CLOCK_MONOTONIC, &t1);
        ns_B[i] = (double)(t1.tv_sec - t0.tv_sec) * 1e9
                + (double)(t1.tv_nsec - t0.tv_nsec);
    }

    double mean_A = 0.0, mean_B = 0.0;
    for (i = 0; i < N_REPS; i++) { mean_A += ns_A[i]; mean_B += ns_B[i]; }
    mean_A /= N_REPS; mean_B /= N_REPS;
    double var_A = 0.0, var_B = 0.0;
    for (i = 0; i < N_REPS; i++) {
        var_A += (ns_A[i] - mean_A) * (ns_A[i] - mean_A);
        var_B += (ns_B[i] - mean_B) * (ns_B[i] - mean_B);
    }
    var_A /= N_REPS; var_B /= N_REPS;
    double se_A = sqrt(var_A / N_REPS), se_B = sqrt(var_B / N_REPS);
    double pooled = sqrt(se_A * se_A + se_B * se_B);
    double t_stat = (pooled > 1e-12) ? (mean_A - mean_B) / pooled : 0.0;
    int sig = (t_stat > 2.0 || t_stat < -2.0) ? 1 : 0;

    printf("{\"hypothesis_id\":\"HYPID\",\"mean_A\":%.1f,\"mean_B\":%.1f,\"variance_A\":%.1f,\"variance_B\":%.1f,\"t_statistic\":%.4f,\"significant\":%s}\n",
           mean_A, mean_B, var_A, var_B, t_stat, sig ? "true" : "false");
    return 0;
}
"""


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

    # -- COMPILE CHECK --------------------------------------------------------
    def _compile_check(self, src: str) -> tuple:
        """Try compiling C source. Returns (ok: bool, error_text: str)."""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".c", mode="w", delete=False) as f:
            f.write(src)
            tmp = Path(f.name)
        try:
            r = subprocess.run(
                ["cc", "-O0", "-x", "c", str(tmp), "-lm", "-o", "/dev/null"],
                capture_output=True, text=True, timeout=15,
            )
            return r.returncode == 0, (r.stderr or r.stdout)
        except Exception as exc:
            return False, str(exc)
        finally:
            tmp.unlink(missing_ok=True)

    # -- FALLBACK VECTOR ------------------------------------------------------
    def _fallback_vector(self, hyp: Hypothesis, sig: str) -> str:
        """Generate a guaranteed-compilable harness without LLM involvement."""
        params = _parse_c_params(sig)
        fn_m = re.search(r'\b([A-Za-z_]\w*)\s*\(', sig)
        fn_name = fn_m.group(1) if fn_m else "target_function"
        stub_sig = re.sub(r'\bstatic\b', '', sig.split('{')[0]).strip().rstrip('{').strip()

        BUF = 64
        decls, init_A, init_B, args_A, args_B = [], [], [], [], []
        for p in params:
            n, t = p['name'], p['type']
            if p['is_array']:
                sz = p['array_size'] or BUF
                decls.append(f"    {t} {n}_A[{sz}], {n}_B[{sz}];")
                init_A.append(f"        memset({n}_A, 0x00, sizeof({n}_A));")
                init_B.append(f"        memset({n}_B, 0x7f, sizeof({n}_B));")
                args_A.append(f"{n}_A"); args_B.append(f"{n}_B")
            elif p['is_ptr']:
                decls.append(f"    {t} {n}_buf_A[{BUF}], {n}_buf_B[{BUF}];")
                init_A.append(f"        memset({n}_buf_A, 0x00, {BUF});")
                init_B.append(f"        memset({n}_buf_B, 0x7f, {BUF});")
                args_A.append(f"{n}_buf_A"); args_B.append(f"{n}_buf_B")
            else:
                decls.append(f"    {t} {n}_A = ({t})0, {n}_B = ({t})1;")
                args_A.append(f"{n}_A"); args_B.append(f"{n}_B")

        decls_str = '\n'.join(decls) if decls else '    /* no params */'
        call_A = f"{fn_name}({', '.join(args_A)})"
        call_B = f"{fn_name}({', '.join(args_B)})"

        return (
            _FALLBACK_TMPL
            .replace("STUB_SIG", stub_sig)
            .replace("DECLS", decls_str)
            .replace("INIT_A", '\n'.join(init_A))
            .replace("INIT_B", '\n'.join(init_B))
            .replace("CALL_A", call_A)
            .replace("CALL_B", call_B)
            .replace("HYPID", hyp.id)
        )

    # -- VECTORIZE ------------------------------------------------------------
    def vectorize(self, hyp: Hypothesis) -> str:
        prompt = STAGE3_PROMPT.read_text(encoding="utf-8")
        hyp_json = json.dumps(asdict(hyp))
        sig = self._signature_for(hyp)
        system = (
            prompt.replace("{hypothesis_json}", hyp_json)
                  .replace("{function_signature}", sig)
                  .replace("{hypothesis_id}", hyp.id)
        )
        user = (
            f"Generate the C timing test for hypothesis {hyp.id}.\n"
            f"Hypothesis JSON: {hyp_json}\n"
            f"Function signature: {sig}"
        )

        raw = call_ollama(CODE_MODEL, system, user)
        src = extract_c_source(raw)

        if not looks_like_c(src):
            retry_system = system + (
                "\n\nYour previous response was invalid. "
                "Return ONLY C source code starting with #include"
            )
            raw = call_ollama(CODE_MODEL, retry_system, user)
            src = extract_c_source(raw)

        ok, err = self._compile_check(src)
        if not ok:
            retry_system = (
                system
                + f"\n\nYour previous response did not compile:\n{err[:400]}\n"
                "Fix all errors. Return ONLY compilable C source starting with #include."
            )
            raw = call_ollama(CODE_MODEL, retry_system, user)
            src = extract_c_source(raw)
            ok, _ = self._compile_check(src)
            if not ok:
                print(f"    WARNING: {hyp.id}: LLM vector did not compile after retry "
                      "— using deterministic fallback.")
                src = self._fallback_vector(hyp, sig)

        suffix = "_fallback" if "fallback: LLM vector" in src else ""
        out = VECTORS_DIR / f"vec_{hyp.id}_{_ts()}{suffix}.c"
        out.write_text(src, encoding="utf-8")
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
            return json.loads(files[-1].read_text(encoding="utf-8")) if files else None

    def _poll_feedback(self, hyp: Hypothesis):
        deadline = time.time() + FEEDBACK_TIMEOUT_S
        while time.time() < deadline:
            # Strict glob: only matches timing_HXXX_<timestamp>.json.
            # Archived files (e.g. ARCHIVED_LEAK5_stale_timing_*.json) won't
            # match because they don't start with "timing_{hyp.id}_".
            matches = list(FEEDBACK_DIR.glob(f"timing_{hyp.id}_*.json"))
            if matches:
                newest = max(matches, key=lambda p: p.stat().st_mtime)
                return json.loads(newest.read_text(encoding="utf-8"))
            print(f"    ...waiting for feedback file timing_{hyp.id}_*.json "
                  f"in {FEEDBACK_DIR} (poll every {POLL_INTERVAL_S}s)")
            time.sleep(POLL_INTERVAL_S)
        print(f"    WARNING: feedback timeout ({FEEDBACK_TIMEOUT_S}s) for "
              f"{hyp.id}; skipping to next hypothesis.")
        return None

    # -- REFINE ---------------------------------------------------------------
    def refine(self, hyp: Hypothesis, timing: dict) -> dict:
        prompt = STAGE2_PROMPT.read_text(encoding="utf-8")
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

        raw = call_ollama(REASON_MODEL, system, user, fmt="json")
        records = None
        try:
            records = extract_json_array(raw)
        except json.JSONDecodeError:
            retry_system = system + (
                "\n\nYour previous response was not valid JSON. Return ONLY "
                "the JSON array starting with [ and ending with ]"
            )
            try:
                raw = call_ollama(REASON_MODEL, retry_system, user, fmt="json")
                records = extract_json_array(raw)
            except json.JSONDecodeError:
                records = None

        # Keep only well-formed record objects — qwen3 + format:json sometimes
        # returns a list of strings or an odd wrapper shape.
        dict_records = [r for r in (records or []) if isinstance(r, dict)]

        _STATUS_VALS = {"PROMOTED", "DEMOTED", "INVALIDATED", "UNCHANGED"}

        if not dict_records and records:
            # Salvage path: qwen3 sometimes emits ["PROMOTED"] (list of strings).
            # Extract the first recognisable status string and build a minimal record.
            for item in records:
                if isinstance(item, str) and item.strip().upper() in _STATUS_VALS:
                    salvaged = item.strip().upper()
                    sig = bool(timing.get("significant"))
                    return {
                        "id": hyp.id,
                        "original_hypothesis": hyp.hypothesis,
                        "status": salvaged,
                        "evidence": (f"Status salvaged from refiner string list; "
                                     f"oracle t={timing.get('t_statistic')}, significant={sig}."),
                        "revised_confidence": (
                            "HIGH" if (salvaged == "PROMOTED" and sig) else
                            "MEDIUM" if salvaged in ("PROMOTED", "DEMOTED") else "NONE"
                        ),
                        "next_test_hint": "Refiner returned string list instead of object array; retry for full evidence.",
                    }

        if not dict_records:
            # Oracle-only fallback — refiner gave nothing usable at all.
            # The oracle measurement IS the ground truth, so use HIGH when significant.
            sig = bool(timing.get("significant"))
            return {
                "id": hyp.id,
                "original_hypothesis": hyp.hypothesis,
                "status": "PROMOTED" if sig else "INVALIDATED",
                "evidence": (f"Refiner JSON unusable; status derived from oracle: "
                             f"t={timing.get('t_statistic')}, significant={sig}."),
                "revised_confidence": "HIGH" if sig else "NONE",
                "next_test_hint": "Re-run refine; qwen3 returned a non-object JSON shape.",
            }

        # find the record matching this hypothesis id (default to first)
        rec = next((r for r in dict_records if str(r.get("id")) == hyp.id),
                   dict_records[0])
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
        with EXPERIMENT_LOG.open("a", encoding="utf-8") as fh:
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
        LOOP_STATE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _load_resume(self):
        if self.resume and LOOP_STATE_FILE.exists():
            prev = json.loads(LOOP_STATE_FILE.read_text(encoding="utf-8"))
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
