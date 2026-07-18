# Rayquaza
Post-Quantum Reconnaissance & Exploitation via AI-Powered Evaluation Research.

A DRDO SAG internship research project. Central question: does LLM-augmented guidance help 
an attacker find weaknesses in post-quantum cryptography implementations (CRYSTALS-Kyber, 
CRYSTALS-Dilithium) faster than classical fuzzing?

## Team
- Track A (Crypto & Systems): Ojas
- Track B (AI & Attack Engine): Vedanth

## Reproducing the experiment

The fastest way to see the core experiment run is Docker:

```bash
git clone <this repo's URL>
cd Rayquaza
docker compose run --rm runner
```

That single command builds the toolchain and liboqs, starts Ollama inside
Docker (no host install needed), detects how much RAM/disk your machine has
free, recommends an appropriately-sized model pair, pulls it, and runs the
LLM adversary engine against the five Kyber512 targets. The only
prerequisite is Docker itself (Docker Desktop on Mac/Windows, Docker Engine
on Linux). Nothing else needs to be installed on your machine; the model
weights are fetched into a Docker-managed volume, not baked into the image
or left on your host filesystem in any other way.

Results land in `shared/feedback/` and `shared/findings/` on your own
machine (bind-mounted, so they survive after the container exits).

Note: `mldsa44_leak1` is not part of this automated flow. See
[docs/reproducing-mldsa.md](docs/reproducing-mldsa.md) for why and how to
run it manually.

For a full walkthrough (what each prompt means, how to read the live
output and the final results, GPU passthrough, troubleshooting), see
[docs/using-the-wizard.md](docs/using-the-wizard.md).

## How to navigate this repo
Read `AGENTS.md` first if you are an AI agent. Humans should start with 
`docs/00_PROJECT_CHARTER.md`, then `tracking/PROGRESS.md` for current status.

## Coordination
All project state lives in `tracking/`. Update it as you work. See AGENTS.md for the protocol.
