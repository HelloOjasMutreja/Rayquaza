# Rayquaza — Platform Vision (living design doc)

**Status:** brainstorming in progress — started 2026-06-19. This is the single source
of truth for the platform idea; we add to it as decisions are made.
**Internal only.** Not for public export. The platform's integrity depends on the
problem set staying confidential (see §4).

---

## 1. What we're building (in one breath)

A **self-sustaining benchmark marketplace** that grades AI models on real,
machine-verifiable **security challenges**. Experts and builders supply the problems;
AI companies pay to have their models graded in tamper-proof cloud sandboxes; the money
flows back out to the people who supplied the problems and the judges who vetted them.
It starts in **post-quantum cryptography** (where we already have a working,
physics-grounded pipeline) and expands across **cybersecurity, quantum, and the broader
security space** — no hard limit.

**"Self-sustaining" means the whole ecosystem keeps turning without the founder having
to operate it** — problems come in, models come in, money circulates, judges are drawn
from the best contributors. It does **not** mean humans are removed. Humans are a
built-in, paid part of the machine (see §2).

---

## 2. The two tracks (the core mental model)

These are completely separate. Conflating them is the mistake to avoid.

### Track 1 — Grading the AI. Fully automatic. Zero humans.
Runs on the cloud. An AI model attempts the live problems; the system scores it
automatically — how many it solved, each problem's own point value, its total score, and
how well it performs **per domain**. No person ever looks at an AI's answer. This is the
benchmark result the paying companies receive.

### Track 2 — Admitting a problem. The *only* place humans act — and they judge the *problem*, never the AI.
A submitted problem must clear a machine check and then a human jury before it's ever used
to test an AI (see §3).

**The clean split:** humans gate the *quality of problems going in*; machines handle
*everything about running and scoring the AI*.

---

## 3. A problem's journey (the admission funnel)

1. **A contributor submits a problem.** ("Contributor" is a working term — see glossary.)
2. **The machine checks it first (automated intake).** Does it set up correctly? Is it
   structured/scaffolded properly? Does it actually run in our environment? Does it meet
   the baseline criteria? If it doesn't fit the expected mold, it may be a genuinely **new
   category** worth looking into rather than an auto-reject.
3. **Only if it passes does it reach the jury** — the judging panel. Each judge reviews the
   *problem*: is it interesting, is it good enough, does it deserve a place. They rate/accept.
4. **On acceptance it is listed into the live benchmark set** — automatically, on the cloud.

---

## 4. Confidentiality (a hard requirement)

The application process, the problem set, and its structure are kept **secret**. AI models
crawl the web; if the problems leak, models can train on them and the benchmark is
poisoned. **Secrecy is the integrity of the test** (contamination resistance). Design
implication: submissions are silent/undisclosed, and the live problems are a held-out
private set — never published.

---

## 5. The economics (as described; full design deferred to the Economics pillar)

- AI companies **pay** to have their models graded (real cloud compute has real cost).
- The revenue splits into: **compute cost + platform profit + payouts** to contributors
  (and judges).
- Payouts are weighted by **domain**, **difficulty** (hard for humans too), and **outcome**.
- **Anti-gaming note (important):** rewarding a contributor *more when the AI fails* — as
  first described — would incentivize submitting impossible/broken problems for payout. The
  fix, to be firmed up later: only reward **"hard but solvable and discriminating"** problems
  — a problem must be provably solvable (its own answer key works) and jury-approved to earn.

---

## 6. Glossary (running — we refine terms as we go)

- **Contributor** — a person who creates and submits a problem. *(working term)*
- **Problem / Challenge** — one machine-verifiable task an AI is graded on.
- **Jury / Judging Panel** — experts who review submitted problems and accept/reject them.
- **Intake check** — the automated validity/setup check a problem must pass before the jury
  sees it.
- **Verifier / Grader** — the small program bundled with a problem that auto-grades an AI's
  attempt.
- **Verdict** — the grader's output: `solved` (yes/no) + `score` (0–1) + `detail`.
- **Benchmark run** — an AI model attempting the live problem set; produces its scores.
- **Held-out / secret set** — the confidential live problems, kept hidden to prevent
  contamination.

---

## 7. How it breaks into buildable pieces (subsystems)

The platform is not one build — it's ~6 independent subsystems. Each gets its own
design → plan → build.

1. **Challenge Contract + Verifier** — what a problem *is* + its auto-grader. *(designing now)*
2. **Intake + Jury curation** — submission, machine checks, panel review, listing.
3. **Secure evaluation sandbox** — tamper-proof, contamination-resistant model runs.
4. **Scoring engine** — per-problem scores → composite + per-domain benchmark.
5. **Economics / payments** — pricing, cost accounting, payout split.
6. **Marketplace orchestration** — the self-running loop + leaderboard.

**Build order:** 1 → 2 & 3 → 4 → 5 → 6, starting narrow with the PQC seed corpus and a
couple of clean-oracle domains, then opening the gates.

---

## 8. Pillar 1 — Challenge Contract + Verifier (decisions so far)

- **A problem is a self-contained folder** holding four things: the task given to the AI,
  the auto-grader, a **secret answer key** (proves the problem is solvable; never shown to
  the AI), and a label (domain, difficulty).
- **Only machine-verifiable problems** are accepted (so Track 1 can grade the AI with no
  humans). Tasks that need human judgement of the *AI's answer* are out of scope.
- **Each problem brings its own grader** ("bring-your-own-verifier") so any domain fits.
- **A problem declares how the AI attempts it:** one submitted answer ("single-shot") now;
  interactive/tool-using ("agentic") later.
- **Every grader outputs the same verdict:** `solved + score + detail`. The whole platform
  consumes only that, so grading logic stays inside the problem and the platform stays generic.
- **Automated admissibility gate (the anti-gaming keystone):** before the jury ever sees a
  problem, the machine checks that the problem's own secret answer key **passes** its grader
  reproducibly, and that a junk attempt **fails**. A problem its own answer can't solve is
  auto-rejected. This is the machine "intake check" of §3, step 2.
- **First thing to build:** `challengekit` — the intake gate packaged as a tool a contributor
  runs on their own machine before submitting — plus two reference graders (the PQC timing
  oracle and a capture-the-flag matcher, proving two very different domains work) and a
  converter that turns our existing PQC targets into this format for an instant seed set.

---

## 9. Open questions / to design next

- Economics + anti-gaming payout rules (the Economics pillar).
- How confidentiality is enforced technically (held-out set mechanics; part of the sandbox).
- The judges' review interface and how contributors/judges are recruited (curation pillar).
- A proper naming/terminology pass (Contributor, Jury, etc.).
