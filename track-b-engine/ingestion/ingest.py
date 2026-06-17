#!/usr/bin/env python3
"""
ingest.py — Track B Stage 1 ingestion pipeline.

Reads a C source file, isolates secret-handling functions, sends them to
codellama:7b with the stage1_analysis.txt prompt, and parses the response
into ranked Hypothesis objects.

Usage: python3 track-b-engine/ingestion/ingest.py <path_to_c_file>
"""

import json
import re
import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "codellama:7b"

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PROMPT_FILE = REPO_ROOT / "track-b-engine" / "prompts" / "stage1_analysis.txt"
FINDINGS_DIR = REPO_ROOT / "shared" / "findings"

# Identifiers that mark a function as secret-handling.
SECRET_TOKENS = [
    "key", "secret", "priv", "cipher", "seed",
    "nonce", "mask", "sk", "dk", "ek",
]

# Confidence ranking for sorting (HIGH first).
CONFIDENCE_RANK = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}

# Secondary-scan patterns: catch leaky functions whose params/locals are NOT
# named with secret tokens (e.g. Kyber's poly_tomsg(), or a bare memcmp on
# secret data). Matched against the comment-stripped function body. Each entry
# is (label, compiled regex). This is the Task-1 fix for the B1 compare() miss.
SECONDARY_PATTERNS = [
    ("nonconstant_comparison", re.compile(r"\b(?:memcmp|strcmp|strncmp)\s*\(")),
    ("secret_dependent_branch", re.compile(r"\bif\b[^\n;{]*KYBER_Q")),
    ("secret_dependent_branch", re.compile(r"\bif\b[^\n;{]*==\s*0\b")),
    ("variable_loop", re.compile(r"\bfor\b[^\n;{]*\b256\b")),
    ("variable_loop", re.compile(r"\bwhile\b[^\n;{]*\bcount\b")),
]


@dataclass
class Hypothesis:
    id: str
    category: str
    location: str
    hypothesis: str
    trigger_condition: str
    confidence: str
    test_vector_hint: str

    @classmethod
    def from_dict(cls, d: dict) -> "Hypothesis":
        return cls(
            id=str(d.get("id", "")),
            category=str(d.get("category", "")),
            location=str(d.get("location", "")),
            hypothesis=str(d.get("hypothesis", "")),
            trigger_condition=str(d.get("trigger_condition", "")),
            confidence=str(d.get("confidence", "")).upper(),
            test_vector_hint=str(d.get("test_vector_hint", "")),
        )


@dataclass
class FunctionInfo:
    signature: str
    name: str
    body: str
    flagged: bool = False
    matched_tokens: list = field(default_factory=list)
    secondary_scan: bool = False
    secondary_matches: list = field(default_factory=list)


class CodeIngester:
    """Preprocess C source and run Stage 1 LLM analysis."""

    # Matches a C function definition: <ret> name(args) { ... opening brace.
    FUNC_RE = re.compile(
        r"(?P<sig>[A-Za-z_][\w\s\*]*?\b(?P<name>[A-Za-z_]\w*)\s*\([^;{]*\))\s*\{",
        re.MULTILINE,
    )

    @staticmethod
    def strip_comments(source: str) -> str:
        # Remove block comments, then single-line comments.
        source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
        source = re.sub(r"//[^\n]*", "", source)
        return source

    @staticmethod
    def _extract_body(source: str, open_brace_idx: int) -> str:
        """Return the {...} body starting at open_brace_idx via brace matching."""
        depth = 0
        for i in range(open_brace_idx, len(source)):
            c = source[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return source[open_brace_idx : i + 1]
        return source[open_brace_idx:]  # unbalanced — return remainder

    def preprocess(self, filepath) -> dict:
        path = Path(filepath)
        raw_source = path.read_text()
        clean = self.strip_comments(raw_source)

        functions = []
        for m in self.FUNC_RE.finditer(clean):
            sig = re.sub(r"\s+", " ", m.group("sig")).strip()
            name = m.group("name")
            body = self._extract_body(clean, m.end() - 1)

            # Flag on tokens appearing in the signature (params) or body
            # (local declarations) as whole words / identifier prefixes.
            haystack = (sig + " " + body).lower()
            matched = [
                t for t in SECRET_TOKENS
                if re.search(r"\b" + re.escape(t) + r"\w*", haystack)
            ]
            info = FunctionInfo(
                signature=sig,
                name=name,
                body=body,
                flagged=bool(matched),
                matched_tokens=matched,
            )
            functions.append(info)

        flagged_functions = [f for f in functions if f.flagged]

        # Secondary scan: look for leak-shaped code patterns (memcmp/strcmp,
        # secret-looking branches, fixed/variable loops) in EVERY function body.
        # - Unflagged functions that match are pulled into the analysis (catches
        #   poly_tomsg() / dummy.c's compare(), whose params carry no secret token).
        # - Flagged functions that match keep the hint too, so a memcmp buried in
        #   a function flagged on 'sk' (e.g. Kyber's crypto_kem_dec) is still
        #   surfaced to the model rather than lost behind the secret-token label.
        secondary_functions = []
        for f in functions:
            hits = []
            for label, pat in SECONDARY_PATTERNS:
                if pat.search(f.body):
                    hits.append(label)
            if hits:
                f.secondary_matches = sorted(set(hits))
                if not f.flagged:
                    f.secondary_scan = True
                    secondary_functions.append(f)

        # Functions actually sent to the analyzer: token-flagged + secondary.
        analyzed_functions = flagged_functions + secondary_functions

        return {
            "raw_source": raw_source,
            "functions": functions,
            "flagged_functions": flagged_functions,
            "secondary_functions": secondary_functions,
            "analyzed_functions": analyzed_functions,
            "line_count": raw_source.count("\n") + 1,
            "filepath": str(path),
        }

    def _call_ollama(self, system_prompt: str, user_content: str, extra_system: str = ""):
        import requests

        system = system_prompt if not extra_system else system_prompt + "\n\n" + extra_system
        payload = {
            "model": MODEL,
            "stream": False,
            # format:json constrains codellama to emit valid JSON — kills the
            # "prose instead of array" failure seen on real Kyber source files.
            "format": "json",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
        }
        resp = requests.post(OLLAMA_URL, json=payload, timeout=180)
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content", "")

    @staticmethod
    def _normalize_to_list(obj):
        """Coerce a parsed JSON value into a list of finding dicts.

        With format:json, codellama may return a bare object instead of an
        array — either a single finding, or a wrapper like {"findings": [...]}
        or {"hypotheses": [...]}. Normalize all of these to a list.
        """
        if isinstance(obj, list):
            return obj
        if isinstance(obj, dict):
            # A wrapper object whose only/first list value holds the findings.
            for v in obj.values():
                if isinstance(v, list):
                    return v
            # Otherwise treat the object itself as a single finding.
            return [obj]
        return []

    @classmethod
    def _parse_json_array(cls, text: str):
        """Parse a JSON array, tolerating stray text, code fences, or a dict."""
        text = text.strip()
        # Strip markdown fences if the model added them despite instructions.
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        try:
            return cls._normalize_to_list(json.loads(text))
        except json.JSONDecodeError:
            pass
        # Fall back to extracting the outermost [...] span.
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            return cls._normalize_to_list(json.loads(text[start : end + 1]))
        raise json.JSONDecodeError("no JSON array found", text, 0)

    def analyze(self, context_dict: dict) -> list:
        try:
            import requests  # noqa: F401
        except ImportError:
            print("ERROR: 'requests' not installed. Run: pip3 install requests")
            sys.exit(1)

        system_prompt = PROMPT_FILE.read_text()

        # Prefer the combined set (token-flagged + secondary-scan); fall back
        # to flagged-only for callers built before the secondary scan existed.
        analyzed = context_dict.get("analyzed_functions")
        if analyzed is None:
            analyzed = context_dict["flagged_functions"]

        if not analyzed:
            print("No secret-handling functions flagged; analyzing full source.")
            user_content = context_dict["raw_source"]
        else:
            blocks = []
            mandates = []   # forceful directives for statically-detected patterns
            for f in analyzed:
                if f.flagged:
                    why = f"flagged on secret token: {', '.join(f.matched_tokens)}"
                    # Surface any leak-shaped construct found in the body so a
                    # memcmp/branch/loop isn't overshadowed by the secret-token label.
                    if f.secondary_matches:
                        why += f"; also contains: {', '.join(f.secondary_matches)}"
                else:
                    why = f"secondary scan: {', '.join(f.secondary_matches)}"
                blocks.append(f"// function: {f.name}  ({why})\n{f.signature} {f.body}")
                # A static scan already PROVED these patterns are present. Make the
                # model emit a finding for each rather than letting the secret-token
                # label pull its single hypothesis elsewhere (the LEAK-5 memcmp miss).
                for cat in f.secondary_matches:
                    mandates.append(
                        f"- Function {f.name}() contains a {cat} construct "
                        f"(confirmed by static scan). You MUST output a separate "
                        f"finding with category \"{cat}\" for it."
                    )

            user_content = "\n\n".join(blocks)
            if mandates:
                user_content = (
                    "MANDATORY FINDINGS — a static analyzer already detected these "
                    "patterns; emit one array element for EACH, plus any others you find:\n"
                    + "\n".join(mandates)
                    + "\n\nSOURCE:\n" + user_content
                )

        raw = ""
        records = None
        try:
            raw = self._call_ollama(system_prompt, user_content)
            records = self._parse_json_array(raw)
        except json.JSONDecodeError:
            # Retry once with a sterner instruction.
            print("First response was not valid JSON; retrying once...")
            retry_note = (
                "Your previous response was not valid JSON. Return ONLY "
                "the JSON array starting with [ and ending with ]"
            )
            try:
                raw = self._call_ollama(system_prompt, user_content, extra_system=retry_note)
                records = self._parse_json_array(raw)
            except json.JSONDecodeError:
                print("ERROR: model did not return valid JSON after retry.")
                print("--- raw response ---")
                print(raw)
                return []

        hypotheses = [Hypothesis.from_dict(r) for r in records]
        hypotheses.sort(key=lambda h: CONFIDENCE_RANK.get(h.confidence, 99))
        return hypotheses

    def save(self, hypotheses: list, output_dir=FINDINGS_DIR) -> str:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = out_dir / f"hypotheses_{timestamp}.json"
        payload = {
            "generated_at": datetime.now().isoformat(),
            "model": MODEL,
            "count": len(hypotheses),
            "hypotheses": [asdict(h) for h in hypotheses],
        }
        out_path.write_text(json.dumps(payload, indent=2))
        return str(out_path)


def _truncate(s: str, n: int = 60) -> str:
    s = s.replace("\n", " ")
    return s if len(s) <= n else s[: n - 1] + "…"


def print_summary_table(hypotheses: list):
    if not hypotheses:
        print("\n(no hypotheses produced)")
        return
    header = f"{'ID':<6} | {'Category':<24} | {'Location':<22} | {'Conf':<6} | Hypothesis"
    print("\n" + header)
    print("-" * len(header))
    for h in hypotheses:
        print(
            f"{h.id:<6} | {h.category:<24} | {_truncate(h.location, 22):<22} | "
            f"{h.confidence:<6} | {_truncate(h.hypothesis, 60)}"
        )


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <path_to_c_file>")
        sys.exit(1)

    filepath = sys.argv[1]
    ingester = CodeIngester()

    print(f"[{datetime.now().isoformat()}] Preprocessing {filepath} ...")
    context = ingester.preprocess(filepath)
    print(
        f"  lines={context['line_count']} "
        f"functions={len(context['functions'])} "
        f"flagged={len(context['flagged_functions'])} "
        f"secondary={len(context.get('secondary_functions', []))}"
    )
    for f in context["flagged_functions"]:
        print(f"    flagged:   {f.name}()  [{', '.join(f.matched_tokens)}]")
    for f in context.get("secondary_functions", []):
        print(f"    secondary: {f.name}()  [{', '.join(f.secondary_matches)}]")

    print(f"\n[{datetime.now().isoformat()}] Calling {MODEL} for Stage 1 analysis ...")
    try:
        hypotheses = ingester.analyze(context)
    except Exception as e:  # noqa: BLE001
        import requests
        if isinstance(e, requests.exceptions.ConnectionError):
            print("Ollama not running. Start with: ollama serve")
            sys.exit(1)
        raise

    print_summary_table(hypotheses)

    saved = ingester.save(hypotheses)
    print(f"\nSaved {len(hypotheses)} hypotheses to: {saved}")


if __name__ == "__main__":
    main()
