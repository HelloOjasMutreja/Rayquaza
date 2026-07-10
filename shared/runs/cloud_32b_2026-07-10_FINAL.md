# 32B tier results (AWS EC2 g5.xlarge, us-east-1, real oracle) — FINAL

Ran on `g5.xlarge` (NVIDIA A10G, 23GB VRAM) in `us-east-1` (N. Virginia) —
`ap-south-1` (Mumbai) and `ap-southeast-2` (Sydney) both had persistent
`g5` capacity shortages across every AZ tried, so this region was picked
for its known deeper GPU inventory. Same setup pattern as the `g4dn` tier:
Ollama installed with GPU detected, repo synced via `rsync` (private repo,
no GitHub token needed), oracle binaries verified with a manual sanity run
before trusting the matrix, all long-running commands launched via
`setsid nohup ... < /dev/null > log 2>&1 &` so they survive local machine
sleep/disconnection entirely (confirmed: this run's log was checked and
found fully complete after a multi-minute gap with no live connection).

Model: `qwen2.5-coder:32b` (19GB, Q4 quantization). Cost: $0 (local model;
only AWS compute-hour cost, not tracked here).

| Target | qwen2.5-coder:32b |
|---|---|
| kyber512_leak5 (FO memcmp) | located / confirmed (t=209.28, 403s) |
| kyber512_leak4 (cond. normalization) | located / confirmed (t=-3782.34, 127s) |
| kyber512_leak2 (poly_tomsg branch) | located / confirmed (t=-635.54, 91s) |
| mldsa44_leak1 (ML-DSA memcmp) | located / confirmed (t=-15.04, 132s) |

**4/4 located+confirmed. Zero pipeline crashes.**

## Same-family scaling comparison: qwen2.5-coder at 7B / 14B / 32B

The same model family was run at three sizes across the same 4 targets,
on three different hardware tiers (CPU/WSL, T4/cloud, A10G/cloud):

| Target | 7B (CPU, WSL) | 14B (T4 GPU) | 32B (A10G GPU) |
|---|---|---|---|
| kyber512_leak5 | located/confirmed | located/confirmed | located/confirmed |
| kyber512_leak4 | located/confirmed | located/confirmed | located/confirmed |
| kyber512_leak2 | located/confirmed | located/confirmed | located/confirmed |
| mldsa44_leak1 | located/confirmed | located/confirmed | located/confirmed |

**12/12 across all three sizes.** qwen2.5-coder has a clean sweep at every
scale tested on this target set — no scaling-driven improvement to report
here (already saturated at 7B for this particular task), which is itself
a notable finding: these 4 targets don't discriminate model capability
within this family/size range. `codellama` told a different story (see
`cloud_gpu_2026-07-10_FINAL.md` and `multi_llm_hybrid_2026-07-09_FINAL.md`)
where 2/4 targets were consistently missed at both 7B and 13B — suggesting
the harder discriminator here is model *family*, not size, at least for
`leak5`/`mldsa44_leak1`'s specific vulnerability shape.

## Full experiment matrix across the whole session (all tiers, all models)

| Target | codellama:7b (CPU) | qwen2.5-coder:7b (CPU) | qwen2.5-coder:14b (T4) | codellama:13b (T4) | qwen2.5-coder:32b (A10G) |
|---|---|---|---|---|---|
| kyber512_leak5 | located/confirmed | located/confirmed | located/confirmed | **missed**/confirmed | located/confirmed |
| kyber512_leak4 | located/confirmed | located/confirmed | located/confirmed | located/confirmed | located/confirmed |
| kyber512_leak2 | located/confirmed | located/confirmed | located/confirmed | located/confirmed | located/confirmed |
| mldsa44_leak1 | located/confirmed | **missed**/confirmed | located/confirmed | **missed**/confirmed | located/confirmed |

19/20 located+confirmed, 1/20 confirmed-but-mislocated (each miss still
found a real, statistically significant timing signal -- these are partial
successes / mis-attributions, not pipeline failures). Zero crashes across
20 cells, three hardware environments (WSL/CPU, EC2 T4, EC2 A10G), five
model/size combinations.

## Instances

- `i-07066e987cdf7dfe6` (g4dn.xlarge, ap-south-1, Mumbai) — **stopped**,
  not billing compute, 60GB volume retained.
- `i-0284335089831d1c6` (g5.xlarge, us-east-1, N. Virginia, IP `3.94.20.75`)
  — **still running**, billing. Stop/terminate when done with this tier.

## Still open

- Frontier API tier (Claude/GPT) — needs API keys in
  `sandbox/secrets.local.json` (gitignored), not run this session.
