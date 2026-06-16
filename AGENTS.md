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

## GitHub Issues — Mandatory Sync
tracking/ISSUES.md and GitHub Issues MUST stay in sync. This is required of all agents on both tracks:

1. **Opening an issue:** Whenever you add an OPEN entry to tracking/ISSUES.md, immediately also
   create the matching GitHub issue using:
   ```
   gh issue create --repo HelloOjasMutreja/Rayquaza --title "..." --body "..."
   ```
   Use the same ID and description. Include file/function/line references in the body.

2. **Closing an issue:** Whenever you mark an entry RESOLVED in tracking/ISSUES.md, immediately
   also close the matching GitHub issue using:
   ```
   gh issue close <number> --repo HelloOjasMutreja/Rayquaza
   ```

3. **Never disclose AI involvement** in any GitHub issue title, body, or comment — no model
   names, no tool names, no attribution lines. Write issues as the project team.

4. `gh` CLI is installed at `C:\Program Files\GitHub CLI\gh.exe` on the Windows host.
   In WSL, call `gh` directly if it is on PATH, or invoke the Windows binary via
   `/mnt/c/Program\ Files/GitHub\ CLI/gh.exe`.

Current open issues and their GitHub numbers are tracked in tracking/ISSUES.md next to each entry.

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

## Track B — LLM Engine Rules
- All AI agents must read tracking/PROGRESS.md and tracking/SYNC.md before any work.
- Tag all Track B entries with [B]. Never edit Track A files or track-a-target/.
- Log every experiment run to EXPERIMENT_LOG.md (append-only).
- Ollama runs locally at http://localhost:11434. Always check reachability before use.
- Models: codellama:7b for code analysis and vector generation; qwen3:8b for reasoning and feedback refinement.
- Prompt templates live in track-b-engine/prompts/. Never inline prompt text in engine code.
- Test vectors go to shared/vectors/. Timing feedback goes to shared/feedback/. Findings go to shared/findings/.
- Mock feedback (track-b-engine/engine/mock_feedback.py) is the stand-in until Track A delivers A2.
