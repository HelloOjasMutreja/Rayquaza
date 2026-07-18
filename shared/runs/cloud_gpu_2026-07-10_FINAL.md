# Cloud GPU tier results (AWS EC2 g4dn.xlarge, Mumbai, real oracle) — FINAL

Ran on an AWS `g4dn.xlarge` (Tesla T4, 15GB VRAM) in `ap-south-1`, launched after
`g5.xlarge` (A10G) hit persistent "insufficient capacity" errors across
ap-south-1, ap-southeast-2 (Sydney), and every AZ tried in both. `g4dn` shares
the same approved "G and VT instances" quota bucket, so no new quota request
was needed. GPU VRAM (15GB) doesn't comfortably fit a true 32B model at good
quantization, so this ran 13B/14B-class code models instead — a genuine
cloud-GPU validation tier, not the originally-planned 32B tier (that stays
blocked on `g5`/`g6` capacity; see below).

Each cell = one full engine run on the real GPU-backed Ollama instance: real
static-scan ingest, real gcc-compiled timing harness (binaries built fresh on
the instance, verified against a manual sanity run before trusting the
matrix), real Welch t-test oracle, real LLM refine verdict. Cost: $0 (all
local/open-weight models on the instance — only AWS compute-hour cost, not
tracked here).

| Target | qwen2.5-coder:14b | codellama:13b |
|---|---|---|
| kyber512_leak5 (FO memcmp) | located / confirmed (t=1937.41, 228s) | **missed** / confirmed (t=2117.58, 227s) |
| kyber512_leak4 (cond. normalization) | located / confirmed (t=-1311.80, 163s) | located / confirmed (t=-1330.41, 157s) |
| kyber512_leak2 (poly_tomsg branch) | located / confirmed (t=-976.44, 134s) | located / confirmed (t=-951.04, 161s) |
| mldsa44_leak1 (ML-DSA memcmp) | located / confirmed (t=-236.99, 141s) | **missed** / confirmed (t=-215.47, 156s) |

- **qwen2.5-coder:14b: 4/4 located+confirmed.**
- **codellama:13b: 2/4 located+confirmed, 2/4 confirmed-but-mislocated** (both
  misses are the same two targets — `leak5` and `mldsa44_leak1` — where the
  smaller `codellama:7b` in last night's WSL run succeeded on `leak5` but not
  on the equivalent local matrix; worth flagging as a possible model-specific
  blind spot on FO/memcmp-style oracles rather than noise, since it's
  consistent across model sizes for this family).
- **Zero pipeline crashes across all 8 cells** — a strong signal the bug
  fixes from last night's WSL debugging session (wait_start regex,
  invoke_oracle cwd, HTTP timeouts, stale-feedback contamination) generalize
  cleanly to a completely different OS/hardware environment, not WSL-specific
  workarounds.
- **~3x faster than CPU/WSL**: cells averaged 130-230s here vs. 400-740s on
  the WSL CPU box for the same targets, as expected from real GPU inference.

## Operational notes from this run

- `g5.xlarge` (the intended 32B-class instance) hit AWS capacity shortages in
  every Mumbai AZ and in Sydney (a second region approved by mistake along
  the way, also confirmed capacity-constrained). This is a real, currently
  unresolved AWS supply issue for the A10G-based `g5` family in these
  regions, not a config problem — `g4dn` was used as a same-quota-bucket
  fallback that had capacity immediately.
- The security group's SSH rule is locked to "My IP" — home ISP issued a new
  dynamic IP partway through this session, which silently blocked
  reconnection (looked like the instance was down; it wasn't). Rule was
  updated to the new IP mid-session. Worth remembering if connectivity drops
  again with no other explanation.
- Long-running remote commands were initially launched attached to the SSH
  session (no `nohup`/`setsid`) — this would have died if the local machine
  slept or the SSH connection dropped for any reason. Fixed by relaunching
  via `setsid nohup ... < /dev/null > log 2>&1 &`, which fully detaches the
  process into its own session, immune to SSH disconnection. Confirmed
  working: the `codellama:13b` 4-cell run completed successfully during a
  ~15 minute window where SSH access was actually down (the IP-change issue
  above), proving the detachment holds.
- `pkill -f sandbox.experiment` is unsafe over SSH: `pkill -f` matches
  against a process's full command line, and `pkill`'s own argv literally
  contains the search string, so it can self-match and kill the SSH session
  that's running it. Use `pkill -f "[s]andbox.experiment"` (bracket trick) or
  match on PID instead.

## Instance still running

`i-07066e987cdf7dfe6` (g4dn.xlarge, ap-south-1b, IP `15.252.16.229` — may
change again if it stops/restarts) is still up and billing. Terminate it via
EC2 console when you're done with this tier, or let me know and I'll do it.

## Still blocked / needs your input

- True 32B tier: needs `g5`/`g5.2xlarge`/`g6` capacity somewhere with actual
  availability — worth checking `us-east-1` or `us-west-2` (historically much
  deeper GPU capacity than APAC regions) if you want to pursue this further;
  would need a fresh quota request scoped to that region.
- Frontier API tier (Claude/GPT): needs your API keys in
  `sandbox/secrets.local.json` (gitignored).
