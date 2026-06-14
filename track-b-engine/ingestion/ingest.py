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

        return {
            "raw_source": raw_source,
            "functions": functions,
            "flagged_functions": flagged_functions,
            "line_count": raw_source.count("\n") + 1,
            "filepath": str(path),
        }

    def _call_ollama(self, system_prompt: str, user_content: str, extra_system: str = ""):
        import requests

        system = system_prompt if not extra_system else system_prompt + "\n\n" + extra_system
        payload = {
            "model": MODEL,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
        }
        resp = requests.post(OLLAMA_URL, json=payload, timeout=180)
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content", "")

    @staticmethod
    def _parse_json_array(text: str):
        """Parse a JSON array, tolerating stray text or code fences around it."""
        text = text.strip()
        # Strip markdown fences if the model added them despite instructions.
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # Fall back to extracting the outermost [...] span.
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise json.JSONDecodeError("no JSON array found", text, 0)

    def analyze(self, context_dict: dict) -> list:
        try:
            import requests  # noqa: F401
        except ImportError:
            print("ERROR: 'requests' not installed. Run: pip3 install requests")
            sys.exit(1)

        system_prompt = PROMPT_FILE.read_text()

        flagged = context_dict["flagged_functions"]
        if not flagged:
            print("No secret-handling functions flagged; analyzing full source.")
            user_content = context_dict["raw_source"]
        else:
            user_content = "\n\n".join(
                f"// function: {f.name}  (flagged on: {', '.join(f.matched_tokens)})\n{f.signature} {f.body}"
                for f in flagged
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
        f"flagged={len(context['flagged_functions'])}"
    )
    for f in context["flagged_functions"]:
        print(f"    flagged: {f.name}()  [{', '.join(f.matched_tokens)}]")

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
