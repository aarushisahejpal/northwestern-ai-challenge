# Handoff: build the embedding layer on the Mac Studio (M3 Ultra)

**Goal:** embed ~388K distinct lobbying free-text strings into
`db/lda_full.duckdb` (it's DuckDB, not sqlite), then carry that ONE file back
to the Linux laptop. Everything else on this machine is disposable afterward.

The script (`skills/lda-corpus-loader/scripts/embed_corpus.py`) auto-detects
Apple Silicon (`mps`). It writes two tables in place — `lobbying_text_embeddings`
and `lobbying_text_map` — and is safe to re-run (CREATE OR REPLACE; no resume:
an interrupted run starts over).

## 1. Setup (~5 min)

```bash
cd <this folder>
python3 -m venv .venv-embed
.venv-embed/bin/pip install torch sentence-transformers duckdb numpy pyarrow einops
```

(torch's default macOS arm64 wheel has MPS support; einops is only needed if
falling back to the nomic model.)

## 2. Smoke test first (~1–2 min)

```bash
.venv-embed/bin/python skills/lda-corpus-loader/scripts/embed_corpus.py \
    --db db/lda_full.duckdb --model Qwen/Qwen3-Embedding-0.6B --limit 2000 --batch 64
```

Expect: `device=mps`, a texts/s rate, and a clean "Done". The script aborts
itself if the embeddings come out NaN (wrong dtype for the hardware) — if that
happens, retry with `--dtype fp32` (slower but always safe) or `--dtype bf16`.
Note the texts/s rate: full run ≈ 388,000 / rate seconds.

## 3. Full run

Model choice (owner preference: NO gated models — do not use the
embeddinggemma default here, it needs a HuggingFace license login):

- **Qwen/Qwen3-Embedding-0.6B — RECOMMENDED.** Ungated; highest retrieval
  quality of everything benchmarked on this corpus (2026-07-14 bake-off,
  branch `experiment/embedding-bakeoff`). Was hopeless on the 4GB Linux GPU
  but should be ~1–3 h on the M3 Ultra.
- Fallback if too slow: `nomic-ai/nomic-embed-text-v1.5` (ungated, ~93% of
  gemma's quality, several× faster than qwen3).

```bash
caffeinate -i .venv-embed/bin/python skills/lda-corpus-loader/scripts/embed_corpus.py \
    --db db/lda_full.duckdb --model Qwen/Qwen3-Embedding-0.6B --batch 64
```

(`caffeinate -i` stops macOS from idle-sleeping mid-run. If the smoke test was
fast, try `--batch 128` — with 256GB unified memory the ceiling is high.)

Progress prints every 5,000 texts with an ETA. IMPORTANT: any earlier smoke
runs left partial tables behind — the full run replaces them completely, which
is expected and fine. Just make sure the FULL run is the LAST run.

## 4. Verify before carrying back (~30 s)

```bash
.venv-embed/bin/python - <<'EOF'
import duckdb
con = duckdb.connect("db/lda_full.duckdb", read_only=True)
n, model = con.execute(
    "SELECT count(*), any_value(model) FROM lobbying_text_embeddings").fetchone()
m = con.execute("SELECT count(*) FROM lobbying_text_map").fetchone()[0]
assert n > 380_000, f"only {n:,} embeddings — a --limit smoke run was last?"
assert m > 1_500_000, f"only {m:,} map rows"
print(f"OK: {n:,} embeddings ({model}), {m:,} map rows")
EOF
```

## 5. Bring back

Copy `db/lda_full.duckdb` (will be ~3.5–4.5 GB) back to the Linux laptop at
`db/lda_full.duckdb`, replacing the one there. Nothing else changed on this
machine matters. Delete `.venv-embed/` and the HuggingFace cache
(`~/.cache/huggingface`) if disk tidiness matters.
