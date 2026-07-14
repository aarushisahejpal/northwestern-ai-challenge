#!/usr/bin/env python3
"""Embedding-model bake-off for the semantic discovery layer (DISPOSABLE).

Compares candidate embedding models on THIS corpus (lobbying free-text +
press releases) before committing to one. Side-by-side with BM25 (the
existing FTS discovery layer) on the same sampled docs.

Scratch tooling: lives in scratch/, never part of the submission repo.
DB is opened read-only; all artifacts stay under scratch/embedding_bakeoff/.

Usage:
  .venv/bin/python bakeoff.py --smoke          # 1 model, 2K docs, ~2 min
  .venv/bin/python bakeoff.py                  # full: 4 models, 20K docs
  .venv/bin/python bakeoff.py --models bge-small gemma --sample 5000
"""

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
# Keep model downloads inside scratch/ so `rm -rf scratch/` removes everything.
import os
os.environ.setdefault("HF_HOME", str(HERE / "hf_cache"))

import duckdb  # noqa: E402
import numpy as np  # noqa: E402

DB = str(HERE / "../../db/lda_full.duckdb")

# Each entry: HF id + how queries/documents must be prefixed (per model card).
# Getting these conventions right is what makes the comparison fair.
MODELS = {
    "bge-small": {
        "hf": "BAAI/bge-small-en-v1.5",
        "query_prefix": "Represent this sentence for searching relevant passages: ",
        "doc_prefix": "",
    },
    "gemma": {  # gated: needs HF login + accepted license
        "hf": "google/embeddinggemma-300m",
        "prompt_query": "query",       # sentence-transformers prompt_name
        "prompt_doc": "document",
        # fp16 NaNs (Gemma3 activation overflow; needs bf16/fp32, and Turing
        # has no bf16) -> fp32 with a small batch to fit 4GB.
        "batch": 8,
    },
    "qwen3": {
        "hf": "Qwen/Qwen3-Embedding-0.6B",
        "prompt_query": "query",       # ships a "query" prompt; docs are plain
        "doc_prefix": "",
        "fp16": True,                  # 0.6B in fp32 + activations OOMs a 4GB card
        "batch": 8,
    },
    "nomic": {
        "hf": "nomic-ai/nomic-embed-text-v1.5",
        "query_prefix": "search_query: ",
        "doc_prefix": "search_document: ",
        "trust_remote_code": True,
    },
}

# Probe queries: each targets a known weakness of the current keyword/BM25
# discovery layer. `expect` is an eyeball hint, not a scored label.
PROBES = [
    {"q": "cryptocurrency and digital asset market regulation",
     "expect": "stablecoin/crypto/virtual currency filings incl. terms BM25 'crypto' misses"},
    {"q": "router security and restrictions on Chinese network equipment",
     "expect": "TP-Link-adjacent filings (lead L020) without the word 'router' required"},
    {"q": "pharmacy middlemen taking a cut of drug prices",
     "expect": "PBM filings phrased as 'pharmacy benefit managers', no keyword overlap"},
]

# Facet-tag weak labels: does a concept query rank curated-tagged docs highly?
# Uses lobbying_issue_mentions (industry lexicon tags) as imperfect ground truth.
FACET_EVAL = {"CRYPTO": "cryptocurrency, digital assets, blockchain, and stablecoin policy"}


def get_sample(con, n, seed_sql="hash(txt)"):
    """Deterministic sample of distinct lobbying texts + how often each is filed."""
    return con.execute(f"""
        SELECT txt, count(*) AS n_rows, min(record_key) AS example_key,
               max(CASE WHEN m.doc_id IS NOT NULL THEN 1 ELSE 0 END) AS tagged_crypto
        FROM lobbying_freetext f
        LEFT JOIN (SELECT DISTINCT doc_id FROM lobbying_issue_mentions
                   WHERE tag = 'CRYPTO') m USING (doc_id)
        GROUP BY txt ORDER BY {seed_sql} LIMIT {n}""").fetchall()


def bm25_topk(con, query, sample_txts, k):
    """BM25 over the sampled texts only (fair comparison: same doc pool)."""
    con.execute("CREATE OR REPLACE TEMP TABLE _sample(txt TEXT)")
    con.executemany("INSERT INTO _sample VALUES (?)", [(t,) for t in sample_txts])
    # Restrict the existing full-corpus FTS index to sampled texts.
    rows = con.execute("""
        SELECT f.txt, max(fts_main_lobbying_freetext.match_bm25(f.doc_id, ?)) AS s
        FROM lobbying_freetext f JOIN _sample s ON s.txt = f.txt
        GROUP BY f.txt HAVING s IS NOT NULL ORDER BY s DESC LIMIT ?""",
        [query, k]).fetchall()
    return [(r[0], r[1]) for r in rows]


def load_model(key):
    from sentence_transformers import SentenceTransformer
    cfg = MODELS[key]
    kw = {}
    if cfg.get("trust_remote_code"):
        kw["trust_remote_code"] = True
    if cfg.get("fp16"):
        import torch
        kw["model_kwargs"] = {"torch_dtype": torch.float16}
    t0 = time.time()
    model = SentenceTransformer(cfg["hf"], device="cuda", **kw)
    # Our texts are short (p99 ~370 tokens); capping bounds activation memory
    # and keeps the doc surface identical across models.
    model.max_seq_length = 512
    print(f"  loaded {cfg['hf']} in {time.time()-t0:.0f}s")
    return model


def encode(model, cfg, texts, is_query):
    kw = {"batch_size": cfg.get("batch", 64), "normalize_embeddings": True,
          "show_progress_bar": False, "convert_to_numpy": True}
    pn = cfg.get("prompt_query" if is_query else "prompt_doc")
    if pn:
        kw["prompt_name"] = pn
    else:
        prefix = cfg.get("query_prefix" if is_query else "doc_prefix", "")
        texts = [prefix + t for t in texts]
    return model.encode(texts, **kw)


def snippet(t, n=90):
    return " ".join(t.split())[:n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*", default=list(MODELS))
    ap.add_argument("--sample", type=int, default=20000)
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--smoke", action="store_true",
                    help="1 model (bge-small), 2K docs — a fast dry run")
    args = ap.parse_args()
    if args.smoke:
        args.models, args.sample = ["bge-small"], 2000

    con = duckdb.connect(DB, read_only=True)
    con.execute("LOAD fts")
    print(f"Sampling {args.sample:,} distinct lobbying texts ...")
    sample = get_sample(con, args.sample)
    txts = [r[0] for r in sample]
    n_tagged = sum(r[3] for r in sample)
    print(f"  {len(txts):,} texts ({n_tagged} carry a curated CRYPTO tag)")

    report = {"sample": len(txts), "models": {}}
    for mkey in args.models:
        cfg = MODELS[mkey]
        print(f"\n=== {mkey} ({cfg['hf']}) ===")
        model = load_model(mkey)
        t0 = time.time()
        doc_vecs = encode(model, cfg, txts, is_query=False)
        dt = time.time() - t0
        rate = len(txts) / dt
        print(f"  embedded {len(txts):,} docs in {dt:.0f}s ({rate:,.0f} docs/s)")
        mrep = {"docs_per_sec": round(rate), "probes": []}

        for probe in PROBES:
            qv = encode(model, cfg, [probe["q"]], is_query=True)[0]
            sims = doc_vecs @ qv
            top = np.argsort(-sims)[:args.k]
            bm = bm25_topk(con, probe["q"], txts, args.k)
            bm_set = {t for t, _ in bm}
            print(f"\n  Q: {probe['q']}\n     (expect: {probe['expect']})")
            print(f"  {'—'*100}")
            print(f"  {'SEMANTIC':<52} | BM25")
            for i in range(args.k):
                left = f"{sims[top[i]]:.3f} {snippet(txts[top[i]], 44)}" if i < len(top) else ""
                right = f"{bm[i][1]:.1f} {snippet(bm[i][0], 40)}" if i < len(bm) else "—"
                print(f"  {left:<52} | {right}")
            sem_set = {txts[i] for i in top}
            overlap = len(sem_set & bm_set)
            print(f"  overlap with BM25 top-{args.k}: {overlap}/{args.k}")
            mrep["probes"].append({
                "query": probe["q"], "overlap_bm25": overlap,
                "semantic_top": [{"score": float(sims[i]), "txt": txts[i][:300],
                                  "example_key": sample[i][2]} for i in top],
                "bm25_top": [{"score": s, "txt": t[:300]} for t, s in bm]})

        # Persist vectors: scoring becomes re-runnable without re-embedding.
        np.save(HERE / "results" / f"vecs_{mkey}.npy", doc_vecs)

        # Weak-label check vs curated CRYPTO tags, at several ranking depths.
        # p@50 saturates once the pool holds >50 tagged docs (a strong model
        # fills its top-50 either way); recall of the WHOLE tagged set at
        # deeper cutoffs + average precision is where models diverge.
        tagged = np.array([bool(r[3]) for r in sample])
        for facet, cquery in FACET_EVAL.items():
            if n_tagged < 5:
                print(f"\n  [{facet}] too few tagged docs in sample to score")
                continue
            qv = encode(model, cfg, [cquery], is_query=True)[0]
            sims = doc_vecs @ qv
            order = np.argsort(-sims)
            ranked_tags = tagged[order]
            p50 = int(ranked_tags[:50].sum())
            scores = {"p@50": p50}
            for depth in (100, 250, 500):
                scores[f"recall@{depth}"] = round(
                    float(ranked_tags[:depth].sum()) / n_tagged, 3)
            # Average precision over the full ranking (single robust number)
            hits_cum = np.cumsum(ranked_tags)
            precs = hits_cum[ranked_tags] / (np.flatnonzero(ranked_tags) + 1)
            scores["avg_precision"] = round(float(precs.mean()), 3)
            print(f"\n  [{facet}] vs curated tags (base {n_tagged}/{len(txts)}): "
                  + "  ".join(f"{k}={v}" for k, v in scores.items()))
            mrep[f"{facet}_scores"] = scores
        report["models"][mkey] = mrep
        # Save after each model (a later model's crash shouldn't lose this one)
        out = HERE / "results" / ("smoke.json" if args.smoke else "full.json")
        out.write_text(json.dumps(report, indent=2))
        # Actually release GPU memory before the next model loads
        del model, doc_vecs
        import gc, torch
        gc.collect()
        torch.cuda.empty_cache()

    out = HERE / "results" / ("smoke.json" if args.smoke else "full.json")
    out.write_text(json.dumps(report, indent=2))
    print(f"\nRaw results -> {out}")


if __name__ == "__main__":
    main()
