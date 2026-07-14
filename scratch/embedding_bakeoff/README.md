# Embedding-model bake-off (2026-07-14)

Disposable experiment (lives in `scratch/`, not part of the submission) comparing
embedding models on this corpus before building the semantic discovery layer.
Setup, hardware constraints, and conclusions below; raw outputs in `results/`.

## Setup

- Doc pool: deterministic samples of distinct `lobbying_freetext` texts (2K/10K),
  identical across models. BM25 (the existing FTS discovery layer) as the fixed
  reference on the same pool.
- Quality metric: weak labels from the curated `lobbying_issue_mentions` CRYPTO
  tags (v1.3 lexicon; precision-oriented, model-independent, deterministic —
  known recall gaps, so scores are directional). Concept query ranked against
  the pool; recall@{100,250,500} of the tagged set + average precision.
  (p@50 saturates once the pool holds >50 tagged docs — the 10K numbers are
  the trustworthy ones.)
- Qualitative probes: crypto / router-ban / PBM queries, semantic top-10 vs
  BM25 top-10 side by side (in `results/*.json`).
- Hardware: GTX 1650 Ti 4GB. Qwen3 fp16 batch 8; Gemma fp32 batch 8 (fp16
  NaNs — Gemma3 activation overflow, no bf16 on Turing); others fp32 batch 64;
  max_seq_length 512 for all.

## Results (10K docs, 131 CRYPTO-tagged, 2026-07-14)

| model                          | docs/s | r@100 | r@250 | r@500 | avg prec |
|--------------------------------|-------:|------:|------:|------:|---------:|
| BAAI/bge-small-en-v1.5         |    216 |  .534 |  .687 |  .794 |     .629 |
| nomic-ai/nomic-embed-text-v1.5 |     45 |  .634 |  .794 |  .893 |     .767 |
| google/embeddinggemma-300m     |     40 |  .695 |  .840 |  .924 |     .825 |

Qwen3-Embedding-0.6B (2K run only): best quality (p@50 22/24 findable) but
4 docs/s on this GPU → ~27h per full-corpus embed → disqualified.

## Conclusions

1. **Winner: google/embeddinggemma-300m** — best quality at nomic's speed;
   full 388K-doc lobbying embed ≈ 2.7h on this hardware.
2. nomic-embed-text-v1.5 is the ungated fallback (~93% of Gemma's avg
   precision, no HF license gate) — keep the embed script model-agnostic.
3. All models diverge from BM25 (top-10 overlap 1–5/10) and find paraphrase
   matches BM25 structurally can't (see the PBM probe in results JSONs) —
   the semantic layer adds real discovery surface.
4. Gemma requires fp32 on Turing-generation GPUs; plan batch/dtype flags.

## Reproduce

Recreate the venv (torch + sentence-transformers + duckdb + numpy + einops),
accept the Gemma license on HF, log in with HF_HOME pointed at a local cache,
then: `python bakeoff.py --models bge-small nomic gemma --sample 10000`.
Large artifacts (venv, HF cache, saved vectors) are deliberately not committed.
