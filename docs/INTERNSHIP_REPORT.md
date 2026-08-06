# Internship Report — Project Rayquaza

**Defence Research and Development Organisation — Scientific Analysis Group (DRDO SAG)**
Interns: Ojas Mutreja, Vedanth Dama
Duration: 8 weeks (2026-06-13 → 2026-06-22 core experiment, paper work continuing to 2026-08)

---

## 1. Why This Project Existed

The starting point was a simple but uncomfortable observation: the world is migrating to
post-quantum cryptography (PQC) because a large enough quantum computer would break RSA and
elliptic-curve encryption via Shor's algorithm. NIST finalised the first PQC standards in 2024 —
**ML-KEM** (formerly CRYSTALS-Kyber) for key exchange and **ML-DSA** (formerly CRYSTALS-Dilithium)
for signatures — and DRDO, like every serious security organisation, is migrating toward them.

But mathematically unbreakable does not mean *implemented safely*. A cryptographic scheme is a
design; the actual deployed artifact is thousands of lines of hand-written, performance-tuned C.
The design can be perfect while the code leaks the secret through a careless habit — most commonly
a **timing side-channel**, where execution time depends on secret data. An attacker who cannot
break the math can instead stand outside with a stopwatch, measure tiny timing differences across
thousands of calls, and reconstruct the secret. This is not hypothetical: the **KyberSlash** bug
(2023) was exactly this class of mistake in real, deployed Kyber code.

That gap — code review missing what math cannot — became our research question, formalised in the
project charter:

> **Does LLM-augmented adversarial guidance provide statistically significant uplift to an
> attacker probing post-quantum cryptography implementations, compared to classical fuzzing and
> manual analysis?**

We were not trying to break the lattice math. We were asking whether an AI reading C source code
could rediscover the kind of implementation mistakes that a human security reviewer eventually
would — faster, and at scale — and whether that beats the industry-standard automated
alternative, coverage-guided fuzzing.

---

## 2. What We Actually Built

The project was split into two coordinated tracks from day one, tracked in `tracking/SYNC.md`:

- **Track A** (targets and ground truth): built the reference crypto implementations, injected
  deliberate, realistic timing-leak mistakes into weakened copies, and built the "stopwatch" —
  a timing oracle harness using Welch's t-test to prove a leak is statistically real (not noise).
- **Track B** (the AI adversary): built the LLM-guided pipeline that reads source code, forms
  hypotheses about where a leak might be, writes a test, and judges the oracle's verdict.

The pipeline itself runs as a closed four-step loop:

1. **Read** — `codellama:7b` reads the C source and produces ranked hypotheses ("this `if` on a
   secret coefficient looks like a leak, here, line 25"). A fast regex-based static scan also
   flags known leak-shaped patterns (like a bare `memcmp`) to steer the model when it misses one.
2. **Write a test** — the model writes a small C timing harness that runs the suspect function
   under two conditions: one that should trigger the leak, one that shouldn't.
3. **Measure** — a plain C program runs that harness 50,000 times and applies Welch's t-test.
   This is the ground-truth oracle — the math decides, not an opinion.
4. **Judge** — `qwen3:8b` reads the oracle's verdict and decides whether the hypothesis should be
   promoted, demoted, or rejected, feeding back into the next cycle.

Crucially, this core pipeline runs entirely on **open-weight models, served locally, with no
internet access** — which is exactly what makes the method usable in classified, air-gapped
environments like DRDO SAG's. A later extension (see §6) tested paid cloud models as a
comparison, but the production pipeline does not depend on them.

To test this without touching anything real, we took **correct reference implementations from
liboqs** and deliberately planted six realistic mistakes — five in Kyber512, one in ML-DSA-44 —
then checked whether the AI could rediscover them from source alone, with no hint about what had
been planted. As a fair classical baseline, we ran **AFL++**, the industry-standard
coverage-guided fuzzer, for 24 hours against the same targets.

---

## 3. The Journey, Week by Week

### Foundations (2026-06-13 → 2026-06-14)
The repository was scaffolded jointly. Track A stood up WSL2/Ubuntu 24.04, built `liboqs` from
source, and verified a full Kyber512 keygen → encapsulate → decapsulate round trip. Track B stood
up the engine skeleton: directory structure, the Ollama-based prompt library for the three
pipeline stages, a mock feedback generator to unblock development before real timing data existed,
and the ingestion pipeline (`ingest.py`) that turns C source into ranked hypotheses. First smoke
test on a dummy target already worked — `codellama:7b` correctly flagged 2 of 3 functions and
correctly ignored the one with no secret-dependent parameters.

### Mapping the target and drawing first blood (2026-06-16)
This was the busiest single day of the internship. Track A read every relevant file in the Kyber512
reference implementation, mapped the full decapsulation call chain, and identified five candidate
timing-leak locations spanning three different hardware/compiler failure categories. A timing
harness was built and validated against the *unmodified* reference implementation — confirming it
was constant-time as expected (|t| < 4), which mattered as a sanity check on the whole methodology.

Then came the first real milestone: **LEAK-5**, a `memcmp` substituted for the constant-time
comparison in the Fujisaki–Okamoto transform (the exact KyberSlash-family bug), oracle-confirmed
at t=78.93. Three more Kyber weaknesses followed the same day — a branch on a secret rounding
decision (LEAK-2, t=-139.91), a normalization loop that branches on the sign of secret NTT
coefficients (LEAK-4, t=-318.58), and a `cmov`-defeat scenario (LEAK-1, t=74.74) — plus the first
ML-DSA-44 target, a comparison substitution in the signature verification path
(MLDSA-LEAK-1, t=116.97). By the end of the day, four weakened targets across two PQC algorithm
families existed with statistically confirmed ground truth.

A parallel finding here mattered a great deal for how we would eventually frame the results: when
Track A patched the *same* memcmp bug directly into liboqs and measured full end-to-end
decapsulation (rather than isolating the comparison), the signal vanished into noise (t=2.52 at
n=50k). The ~3ns leak was real, but only visible when isolated by an oracle — a finding that
shaped the whole "oracle isolates the signal, the LLM identifies the pattern" methodology.

### Confirming the hardware boundary (2026-06-16)
Track A traveled the hardware axis, too: LEAK-3 (a branch on the sign of a secret NTT coefficient
inside `basemul()`) was rebuilt and run on real AWS Graviton2 ARM hardware, confirming t=-3956.26 —
extremely significant — while the same code path is immune on x86-64, where the compiler emits a
constant-time `cmov` instead of a branch. This became one of the project's most useful practitioner
findings: a security audit run only on ARM would catch a leak that's invisible on x86, and vice
versa. The same asymmetry reappeared later with `memcmp`: the ML-DSA comparison leak measures
cleanly on x86-64 (byte-by-byte loop with a genuine early exit) but is invisible on macOS/arm64,
because `-O2` on ARM compiles a 32-byte `memcmp` into a fixed-width NEON instruction sequence with
no real early-exit path to leak through — confirmed independently by both tracks and logged as a
formal open-coordination item, then resolved by re-running the oracle on WSL2/x86 (t=164.30).

### The adversary loop goes live (2026-06-17)
With four confirmed Kyber targets and one ML-DSA target in hand, Track B ran the live adversary
loop for the first time against real oracles instead of mocks. The result, run leak by leak:

- **LEAK-2, LEAK-3, LEAK-4** — all rediscovered **autonomously**: `codellama:7b` correctly
  categorized the vulnerability class (`secret_dependent_branch`) and pinpointed the exact
  function and line, with no hints.
- **LEAK-1** — also rediscovered autonomously once the focused single-function test target was
  corrected to match the real harness injection.
- **LEAK-5** (the `memcmp`-class comparison bug) — the model **missed it unaided**. On the full
  source it fixated on key generation; on the focused target it fixated on an unrelated copy
  branch and never flagged the comparison, even with passive hints in the prompt. This is the
  origin of the project's central nuance: not every leak class is equally learnable by a small
  local model.

The fix that got LEAK-5 caught was a **static regex scan** for patterns like a bare `memcmp` call,
which — when triggered — prepends a "MANDATORY FINDINGS" directive to the LLM's prompt, injecting
the scanner's categorical conclusion directly into the model's instructions. With that hint,
LEAK-5 was found and oracle-confirmed (t=141). This is why the final headline is reported
carefully: **4 of 5 Kyber leaks were rediscovered fully autonomously; the fifth required
static-analysis guidance** — and the decision log (`docs/03_DECISIONS.md`) documents explicitly
why we chose to report it this way rather than round up to "5/5" or discard the hint-assisted run.

Along the way this same day, Track A discovered that codellama:7b (the 7-billion-parameter local
model) reliably fails on *full* Kyber source files: it returns prose instead of JSON on 361-line
files, hits Ollama's timeout on 338-line files, and fixates on the wrong function in a 92-line
file. The fix — used for the rest of the internship — was to give the small model **single-function
focused targets** rather than whole translation units, with a note in the paper that larger
context-window models (tested later in the multi-LLM extension) might close this gap.

### Fighting the engine's own bugs (2026-06-17 → 2026-06-19)
Getting a clean, reproducible run out of the pipeline took real debugging, most of it on Track B's
side:
- A stale-checkout scare: Track B reported that ML-DSA's REPS amplification loop and two Kyber
  targets (leak1/leak3) were "missing." Investigation showed both were already committed to
  `main` — Track B's fork was simply behind. This cost time but also surfaced a genuine
  quantization bug (`(now_ns()-t0)/REPS` was truncating a sub-nanosecond signal to integers),
  which Track A fixed properly rather than dismissing.
- The refinement judge (`qwen3:8b`) returned malformed JSON — a bare `["PROMOTED"]` string list
  instead of an object — roughly half the time. Fixed with a string-salvage parser and an explicit
  WRONG/RIGHT example pair added to the refinement prompt.
- The feedback poller matched hypothesis IDs by substring, so it would pick up stale archived
  feedback files from earlier sessions and silently corrupt a run. Fixed to a strict filename
  prefix match.
- The stage-3 test-vector writer originally asked the 7B model to generate a full C harness from a
  narrative spec — it couldn't reliably do this from scratch. The fix was to rewrite the prompt as
  a fill-in-the-blank skeleton with all boilerplate pre-written, add a compile-check step after
  every LLM call, and fall back to a deterministic (non-LLM) harness generator on a second compile
  failure.

None of these were showstoppers, but together they are the difference between a demo and a
result you can put statistics behind — and they're the reason the engine's final numbers can be
trusted.

### Proving the classical baseline is blind (2026-06-18 → 2026-06-19)
While Track B was closing engine bugs, Track A ran the fair comparison: **AFL++ 4.09c**, in
persistent mode with ASAN, for a full 24 hours (~120 million executions) against all four Kyber
targets. The result was unambiguous and became the project's headline finding: **zero crashes on
every target** — expected, since a timing leak is not a memory-safety bug, but the more important
result was structural. AFL++'s coverage map for the LEAK-5 (`memcmp`) target was **byte-for-byte
identical** to the clean baseline (2 corpus paths each) after 120 million runs. The branch-based
leaks (LEAK-2/LEAK-4) did produce larger corpora (20 and 18 paths) because they add reachable code
edges, but AFL still had no way to identify *which* of those paths represented a timing leak versus
ordinary control flow. Coverage-guided fuzzing, by design, cannot see a dimension that doesn't
change which code executes — only how long it takes. The LLM adversary loop, by contrast, both
located and oracle-confirmed the exact same LEAK-5 vulnerability that AFL's 120 million executions
never touched.

### Closing the loop (2026-06-19 → 2026-06-22)
By 2026-06-19, the ML-DSA oracle was reconfirmed on WSL2/x86 (t=164.30, closing the last open
coordination question about macOS/arm64 portability), the engine bugs were fixed, and the
LLM-vs-AFL++ comparison was written up. On 2026-06-22 the core experiment was declared complete:
**4 of 5 Kyber leaks rediscovered autonomously, 1 of 5 scanner-directed; all six planted targets
oracle-confirmed; AFL++ found zero timing leaks in 24h/120M executions.**

---

## 4. Writing It Up

With the experimental result locked, the remaining work was turning it into a defensible paper.
The paper (`docs/paper/paper.md`) went through a full restructure from an ad-hoc 9-section layout
into the standard academic format: **Abstract → Introduction → Literature Review → Methodology →
Results → Discussion → Conclusion**. This involved:

- Splitting the old combined "threat model / architecture / experimental setup" section into a
  proper Methodology section, and pulling technical background (Kyber, ML-DSA, TVLA math) forward
  into the Introduction so a reader doesn't need prior PQC knowledge to follow the rest.
- Rewriting Related Work as a genuine Literature Review with five sub-sections (timing
  side-channels in PQC, LLMs for security, formal constant-time verification, coverage-guided
  fuzzing, and how Rayquaza positions itself against all of them).
- Resolving every `[REF-*]` citation placeholder against real literature — 14 in total. This
  included correcting three factual errors that had crept into early drafts: Hermelink et al. was
  attributed to ASIACRYPT when it was actually published at INDOCRYPT 2021; Ravi et al. was
  attributed to TCHES 2019 when the correct venue is ACM TECS 2023; and the LLM-VULN citation had
  the wrong author name (corrected to David Noever, arXiv 2308.10345). One reference (originally a
  mismatched citation about heap exploitation) was replaced entirely with DIFFUZZ (Nilizadeh et
  al., ICSE 2019), which actually matches what the paper describes — differential fuzzing guided
  toward secret-dependent code paths.
- Adding a documented future-work section for the multi-LLM comparison (see §6 below).

---

## 5. The Rename

Partway through the paper work, the project's working name **PQ-REAPER** was formally replaced
with **Rayquaza** everywhere in the repository — code comments, CLI banners, test fixtures, the
paper title, the experiment log header, and planning docs — five files in total. The paper's
abstract briefly retained an invented backronym ("Post-Quantum Reasoning-Enhanced Adversarial
Pipeline...") which was removed once we confirmed Rayquaza is a codename, not an acronym.

---

## 6. Beyond the Core Result: Does a Bigger Model Fix the Gap?

The one soft spot in the headline result was LEAK-5 needing a hint. The obvious follow-up
question — is that a limitation of using a small, free, local model, or would a much larger,
expensive model simply catch it unaided? — became a dedicated extension, documented in the
plain-English primer as Part 4.5 and in the paper as new §5.5 / a full results section.

We ran the same four-stage pipeline against **18 different models** in one long overnight run,
spanning the original free local model, mid-size models on rented cloud GPUs, and the most capable
paid flagship tiers from both Anthropic and OpenAI. Every model got identical source code,
identical rules, identical scoring — no model-specific tuning.

**The honest answer: paying more does not fix it.**
- Every single model — cheap or expensive, local or cloud — caught 100% of the
  `secret_dependent_branch`-class leaks. Zero misses, zero exceptions, across all 18 models. That
  part of the original result holds up completely regardless of model choice.
- On the harder `memcmp`-style (`nonconstant_comparison`) leaks, accuracy dropped to 64% overall
  and did **not** improve with price. The single most expensive model in the study missed one of
  the two hard cases; the single cheapest paid model tied for the best score of any model tested,
  at a combined cost of about one and a half cents for all four test cases.
- One of Anthropic's most capable models flatly refused to look at the code at all, flagging it as
  sensitive "cyber" content — even though every other model, including 16 separate other attempts,
  analysed the exact same kind of function without objection. In this one case, the most capable
  model in the study was also the least usable.

We then re-ran a control to make sure the hint itself wasn't doing all the work by accident:
five models — one small free one, and the four most expensive cloud models — were asked to find
the hardest bug completely unassisted, with no MANDATORY-directive nudge at all. **Every single
one missed it**, including three models that had found the identical bug correctly moments earlier
when given the one-line hint. This settles the question cleanly: the hint is not a crutch that a
stronger model would outgrow on its own — it is doing real, necessary work that no amount of
additional model scale currently replaces. (One partial exception: on an easier variant of the
same bug class, the expensive cloud models did succeed unaided, while the small free model still
needed the hint — so scale helps somewhat, just not enough to close the gap on the hardest case.)

Practical takeaway for anyone building a tool like this: don't assume the priciest model is
automatically the right choice. For this specific job — reading real cryptographic code and
spotting a subtle non-constant-time comparison — a free or near-free model performed as well as,
and sometimes better than, models costing far more per call.

---

## 7. Where Things Stand Now

As of the last tracking update:

- All six planted vulnerabilities (five Kyber512, one ML-DSA-44) have statistically confirmed
  ground truth via the Welch t-test oracle.
- The LLM adversary loop has been run live against all six; the autonomous-vs-scanner-directed
  breakdown (4/5 Kyber autonomous, 1/5 hint-assisted; ML-DSA oracle confirmed cross-scheme) is
  finalized and documented with its rationale in `docs/03_DECISIONS.md`.
- The 24-hour AFL++ baseline comparison is complete and shows zero detections against every
  target, establishing the core "coverage fuzzing is structurally blind to timing" result.
- The paper is restructured into standard academic form with all citations resolved and the
  multi-LLM extension written up as a full results section plus documented future work.
- Remaining open items are administrative rather than experimental: an optional formal DOI lookup
  for one secondary tool citation (AutoAudit) if one surfaces later, and packaging the supervisor
  briefing materials (paper, bank-analogy briefing, experiment log, progress log, project charter,
  decision log) as PDFs for review.

Two interns, eight weeks, six confirmed vulnerabilities, one clear structural finding about why
classical fuzzing can't see timing bugs, and — the part that surprised us most — clear evidence
that for this specific reading-and-spotting task, spending more money on a bigger model buys you
almost nothing.
