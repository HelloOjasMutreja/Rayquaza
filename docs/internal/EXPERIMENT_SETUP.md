# Multi-LLM Experiment — Setup Runbook (AWS GPU + Frontier APIs)

**Internal.** A start-to-finish guide to running the paid tiers of the multi-LLM scale
experiment efficiently — so no GPU hours or API credits are wasted. Follow top to bottom.

**The experiment question:** does the `nonconstant_comparison` (memcmp) blind spot shrink as
model scale grows? We run each model on a small target subset in **autonomous mode**
(`--mode autonomous`, i.e. `RAYQ_STATIC_SCAN=0`) and record whether it finds the memcmp leak
*unaided*.

**Order of operations (cheapest first):**
1. Tier 1 — local 7B/13B models on the laptop ($0). *Already set up; running separately.*
2. Tier 2 — one big open-weight model (32B) on a rented AWS GPU (~$2–4).
3. Tier 3 — one or two frontier models via API (~$1–4).

**Total realistic spend: ~$5–10.** Keep ~$15–20 available as buffer.

---

## ⚠️ DO THIS FIRST — AWS GPU quota (can take up to 24–48 h to approve)

New AWS accounts have a **quota of 0 vCPUs for GPU (G-family) instances**. You cannot launch a
GPU instance until AWS approves an increase. Request it *now* so it's ready when you are:

1. AWS Console → search **Service Quotas** → **Amazon EC2**.
2. Find **"Running On-Demand G and VT instances"** (it's measured in **vCPUs**, not instances).
3. **Request increase** → enter **8** (a `g5.xlarge` uses 4 vCPUs; 8 gives headroom). Submit.
4. Approval is often minutes but can be up to a day. Do not proceed to §2 until it shows
   **Applied quota ≥ 4**.

Pick a region with `g5` availability near you. For India, **`ap-south-1` (Mumbai)** works;
`us-east-1` is cheapest. Do everything in one region.

---

## Tier 3 — Frontier API keys (do this while waiting for quota; it's quick)

These are **separate from any Claude Pro / ChatGPT Plus subscription** — those do not include
API access.

### Anthropic (Claude)
1. Go to **console.anthropic.com** (NOT claude.ai). Sign in / create an organisation.
2. **Settings → Billing** → add a card → **buy credits** (minimum ~$5 is plenty).
3. **API Keys → Create Key** → copy the `sk-ant-...` value (shown once).
4. Model ID: use the current Sonnet (good cost/capability balance). Copy the exact model string
   from **docs.anthropic.com → Models** (e.g. a `claude-sonnet-...` id). Sonnet, not Opus, keeps
   cost down; Opus optional as an absolute ceiling.

### OpenAI (GPT-4o) — optional second frontier point
1. **platform.openai.com** → sign in → **Settings → Billing** → add a card → add ~$5 credit.
2. **API keys → Create new secret key** → copy the `sk-...` value.
3. Model ID: `gpt-4o`.

### Wire the keys in (local, gitignored — never committed)
Create `sandbox/secrets.local.json` in the repo:
```json
{
  "anthropic": "sk-ant-...",
  "openai": "sk-..."
}
```
Verify a key works (cheap — one tiny call):
```
python -c "from sandbox.gateway.router import Router; from sandbox import config; \
r=Router(keys={p:config.api_key(p) for p in ('anthropic','openai') if config.api_key(p)}); \
print(type(r.provider_for('claude-sonnet-4-5')).__name__)"
```
Expected: `AnthropicProvider` (means the key loaded and routing works).

### Run the frontier tier (fast — minutes)
```
python -m sandbox.experiment --models <claude-model-id> gpt-4o \
  --targets kyber512_leak5 mldsa44_leak1 kyber512_leak4 --mode autonomous
```
Each run prints its `$` cost; the results file totals it. Expect **$1–4** for both models.

---

## Tier 2 — Big open-weight model (32B) on an AWS GPU

### 2.1 Launch the instance (AWS Console → EC2 → Launch instance)
- **Name:** `rayquaza-gpu`
- **AMI:** search Community/AWS AMIs for **"Deep Learning Base OSS Nvidia Driver GPU AMI (Ubuntu 22.04)"**
  — it ships with NVIDIA drivers, saving a painful install. (Plain Ubuntu 22.04 also works but
  then you must install the driver yourself.)
- **Instance type:** **`g5.xlarge`** (1× A10G 24 GB GPU, 4 vCPU, 16 GB RAM) — fits a 32B Q4 model
  on the GPU. (~$1.0/hr in us-east-1; a bit more in ap-south-1.) Do **not** use `g4dn.xlarge` — its
  16 GB GPU is too small for 32B.
- **Key pair:** Create a new key pair → download `rayquaza.pem` → keep it safe. (`chmod 400 rayquaza.pem`)
- **Network/security group:** allow **SSH (port 22) from *My IP* only**. Nothing else.
- **Storage:** change the root volume to **60 GB gp3** (32B model ≈ 20 GB + OS + repo).
- **Launch.** Note the instance's **Public IPv4 address**.

### 2.2 Connect
```
ssh -i rayquaza.pem ubuntu@<PUBLIC_IP>
```
Confirm the GPU is visible:
```
nvidia-smi        # should list an A10G
```

### 2.3 Set up the box
```
# Ollama (auto-uses the GPU when drivers are present)
curl -fsSL https://ollama.com/install.sh | sh

# tools the pipeline + oracle need
sudo apt-get update && sudo apt-get install -y git gcc make python3-pip
pip3 install requests

# pull the 32B open-weight coder model (~20 GB — this is the slow step)
ollama pull qwen2.5-coder:32b
```

### 2.4 Get the repo onto the box
The repo is **private**, so pick one:
- **Option A (no creds on the box, cleanest):** from your laptop,
  `scp -i rayquaza.pem` a tarball of the repo up, or use `git archive | ssh ... tar x`.
- **Option B:** `git clone` with a GitHub Personal Access Token
  (`git clone https://<PAT>@github.com/HelloOjasMutreja/Rayquaza.git`).

Then build the standalone oracle harnesses (self-contained C, no liboqs needed):
```
cd Rayquaza
for t in leak2 leak4 leak5; do (cd track-a-target/targets/kyber512_$t && make); done
(cd track-a-target/targets/mldsa44_leak1 && make)
```

### 2.5 Run the 32B tier
Everything runs locally on the box (Ollama on the GPU + engine + oracle):
```
python3 -m sandbox.experiment --models qwen2.5-coder:32b \
  --targets kyber512_leak5 mldsa44_leak1 kyber512_leak4 --mode autonomous
```
On an A10G this is fast (seconds per model call). Whole run ≈ 15–30 min.

### 2.6 Pull the results back to your laptop
```
scp -i rayquaza.pem "ubuntu@<PUBLIC_IP>:~/Rayquaza/shared/runs/experiment_*.json" .
scp -i rayquaza.pem "ubuntu@<PUBLIC_IP>:~/Rayquaza/shared/runs/experiment_*.md" .
```

### 2.7 ⚠️ COST STOP — terminate the instance immediately
The GPU bills **per hour while running**. The moment results are pulled:
- EC2 Console → select `rayquaza-gpu` → **Instance state → Terminate** (fully deletes it), **or**
  **Stop** (keeps the disk for ~$0.08/GB/month if you might reuse it soon).
- Confirm the instance shows **terminated/stopped**. Double-check the EC2 dashboard shows **0
  running instances**.

**Efficiency tips (to keep GPU cost to ~$2–4):** do §2.3–2.6 in one uninterrupted session; don't
leave the instance idle while you go do something else; terminate the second you have the files.

---

## After all tiers: what happens with the results

Each tier writes `shared/runs/experiment_*.{json,md}` (a model × target matrix of
located/confirmed/t). Hand those files back and they fold into:
- a new **paper table** (autonomous detection rate by model size/lab), and
- a new **figure** (does the memcmp blind spot close with scale?),
turning §5.5 "future work" into a real results section.

---

## Cost summary

| Tier | What | Realistic | Buffer |
|---|---|---|---|
| 1 | Local 7B/13B (laptop) | $0 | $0 |
| 2 | `g5.xlarge` GPU, ~2–3 h incl. setup | $2–4 | $8 |
| 3 | Claude + GPT-4o API, ~10 runs | $1–4 | $6 |
| | **Total** | **$5–10** | **~$15–20** |
