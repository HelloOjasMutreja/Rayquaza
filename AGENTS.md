# Instructions for All AI Agents

This file governs how every AI agent (Claude, coding agents, etc.) on BOTH tracks operates 
in this repository. Read it fully at the start of every session before doing any work.

## Context
Rayquaza is a two-person DRDO SAG research project. It investigates whether LLM-augmented 
guidance helps an attacker find weaknesses in post-quantum cryptography (Kyber, Dilithium) 
faster than classical fuzzing. Track A owns the crypto target and measurement; Track B owns 
the LLM attack engine and fuzzing baseline.

## Read-Before-Acting Protocol
At the start of EVERY session, read these files in order:
1. AGENTS.md (this file)
2. tracking/PROGRESS.md — current state: Done / In Progress / Blocked
3. tracking/SYNC.md — cross-track handoffs and dependencies
4. tracking/ISSUES.md — open problems and questions
5. The relevant track plan: track-a-target/TRACK_A_PLAN.md OR track-b-engine/TRACK_B_PLAN.md

## Update-After-Acting Protocol
After completing any unit of work, update:
- tracking/PROGRESS.md — move items between Done / In Progress / Blocked. Tag [A] or [B].
- tracking/EXPERIMENT_LOG.md — append a timestamped entry for ANY experiment or run.
- tracking/SYNC.md — if you produced something the other track needs, or need something.
- tracking/ISSUES.md — log any new problem, bug, or open question.

## Rules
- Tag every tracking entry with [A] or [B] to show which track it belongs to.
- Keep entries concise and timestamped (use ISO dates: YYYY-MM-DD).
- Never edit the OTHER track's plan file or invade their directory.
- If blocked on a cross-track dependency, log it in SYNC.md and PROGRESS.md. Do not work 
  around it silently — surface it.
- EXPERIMENT_LOG.md is append-only. Never delete or rewrite past entries.
- When unsure about scope or a design decision, log it in ISSUES.md and docs/03_DECISIONS.md 
  rather than guessing.
- This is security research conducted in a controlled, authorized DRDO context against our 
  own deliberately-weakened targets. Stay within that scope.

## The Critical Dependency
Track B's attack engine (phase B3) depends on Track A delivering: a timing harness (A2) and 
deliberately-weakened Kyber targets (A3). This is the project's critical path. Track A's 
weeks 1-2 are top priority. Track B builds against mocks until those land.
