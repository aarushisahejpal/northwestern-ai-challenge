#!/usr/bin/env python3
"""Build the semantic-search layer: embed distinct lobbying free-text into the DB.

Adds two tables (in place, CREATE OR REPLACE — safe to re-run after a corpus
rebuild, mirroring add_lobbying_freetext.py):

  lobbying_text_embeddings  one row per DISTINCT lobbying_freetext.txt:
                            (txt_hash, model, dim, vector FLOAT[dim]).
                            Identical activity descriptions are refiled quarter
                            after quarter (1.53M rows -> ~388K distinct texts),
                            so embedding distinct texts is ~4x cheaper.
  lobbying_text_map         doc_id -> txt_hash. Joins every embedding back to
                            lobbying_freetext rows, which carry the record_key
                            + src pointers — preserving the repo invariant that
                            every queryable row resolves to a citable raw record.

Role: DISCOVERY ONLY (same posture as the FTS/BM25 index this complements).
Semantic neighbors propose vocabulary and leads; findings cite records via the
deterministic keyword serving tables, never via embedding similarity.

Model: google/embeddinggemma-300m by default — chose via the 2026-07-14
bake-off (branch experiment/embedding-bakeoff): best weak-label retrieval
quality per unit time on a 4GB GPU (avg precision .825 vs nomic .767 /
bge-small .629). It is HF license-gated; --model nomic-ai/nomic-embed-text-v1.5
is the ungated fallback (~93% of the quality). The model name is stamped on
every row, so switching models is just a re-run.

Requires (NOT in requirements.txt — semantic layer is optional, like tesseract):
  pip install torch sentence-transformers  (+ accept the Gemma license on HF
  and `hf auth login` if using the default model)

Usage:
  python embed_corpus.py --db db/lda_full.duckdb                  # full (~2.7h GPU)
  python embed_corpus.py --db db/lda_full.duckdb --limit 5000     # smoke slice
  python embed_corpus.py --db db/lda_full.duckdb --model nomic-ai/nomic-embed-text-v1.5
"""

import argparse
import sys
import time
from pathlib import Path

import duckdb
import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

# Per-model encode settings, learned the hard way on a 4GB GTX 1650 Ti
# (see scratch/embedding_bakeoff or branch experiment/embedding-bakeoff):
# Gemma fp16 emits NaNs (Gemma3 activation overflow; Turing has no bf16), so
# it runs fp32 with a small batch. Unlisted models get conservative defaults.
MODEL_SETTINGS = {
    "google/embeddinggemma-300m": {"batch": 8, "dtype": "fp32",  # fp16 NaNs (no bf16 on Turing)
                                   "prompt_query": "query", "prompt_doc": "document"},
    "nomic-ai/nomic-embed-text-v1.5": {"batch": 64, "dtype": "fp32",
                                       "query_prefix": "search_query: ",
                                       "doc_prefix": "search_document: ",
                                       "trust_remote_code": True},
    "BAAI/bge-small-en-v1.5": {"batch": 64, "dtype": "fp32",
                               "query_prefix": "Represent this sentence for "
                                               "searching relevant passages: ",
                               "doc_prefix": ""},
    "Qwen/Qwen3-Embedding-0.6B": {"batch": 16, "dtype": "fp16",
                                  "prompt_query": "query"},
}
DEFAULT_MODEL = "google/embeddinggemma-300m"


def load_model(name, device=None, batch=None, dtype=None):
    """Batch/dtype defaults were tuned on a 4GB GTX 1650 Ti; on bigger
    hardware (e.g. Apple Silicon with lots of unified memory) raise --batch
    substantially. The NaN guard in main() catches a wrong dtype choice."""
    import torch
    from sentence_transformers import SentenceTransformer
    cfg = dict(MODEL_SETTINGS.get(name, {"batch": 16, "dtype": "fp32"}))
    if batch:
        cfg["batch"] = batch
    if dtype:
        cfg["dtype"] = dtype
    kw = {}
    if cfg.get("trust_remote_code"):
        kw["trust_remote_code"] = True
    dt = {"fp16": torch.float16, "bf16": torch.bfloat16}.get(cfg.get("dtype"))
    if dt:
        kw["model_kwargs"] = {"torch_dtype": dt}
    device = device or ("cuda" if torch.cuda.is_available()
                        else "mps" if torch.backends.mps.is_available()
                        else "cpu")
    model = SentenceTransformer(name, device=device, **kw)
    model.max_seq_length = 512  # p99 lobbying text ~370 tokens
    return model, cfg, device


def encode(model, cfg, texts, is_query=False):
    kw = {"batch_size": cfg.get("batch", 16), "normalize_embeddings": True,
          "show_progress_bar": False, "convert_to_numpy": True}
    pn = cfg.get("prompt_query" if is_query else "prompt_doc")
    if pn:
        kw["prompt_name"] = pn
    else:
        prefix = cfg.get("query_prefix" if is_query else "doc_prefix", "")
        if prefix:
            texts = [prefix + t for t in texts]
    return model.encode(texts, **kw)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, required=True)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--limit", type=int, help="embed only the first N distinct "
                    "texts (deterministic hash order) — smoke/testing")
    ap.add_argument("--batch-flush", type=int, default=5000,
                    help="rows per DB write")
    ap.add_argument("--device", choices=["cuda", "mps", "cpu"],
                    help="override auto-detection (cuda > mps > cpu)")
    ap.add_argument("--batch", type=int, help="override the model's default "
                    "encode batch size (raise on big-memory hardware)")
    ap.add_argument("--dtype", choices=["fp32", "fp16", "bf16"],
                    help="override the model's default dtype")
    args = ap.parse_args()

    con = duckdb.connect(str(args.db))
    limit = f"LIMIT {args.limit}" if args.limit else ""
    # md5 of the exact text is the stable join key; hash() is not stable
    # across duckdb versions, md5 is.
    print("Collecting distinct texts ...")
    con.execute(f"""
        CREATE OR REPLACE TABLE lobbying_text_map AS
        SELECT doc_id, md5(txt) AS txt_hash FROM lobbying_freetext
        {"" if not args.limit else
         f"WHERE md5(txt) IN (SELECT md5(txt) FROM (SELECT DISTINCT txt FROM lobbying_freetext ORDER BY md5(txt) {limit}))"}
    """)
    distinct = con.execute(f"""
        SELECT md5(txt) AS h, any_value(txt) FROM lobbying_freetext
        GROUP BY h ORDER BY h {limit}""").fetchall()
    print(f"  {len(distinct):,} distinct texts to embed "
          f"({con.execute('SELECT count(*) FROM lobbying_text_map').fetchone()[0]:,} doc rows mapped)")

    print(f"Loading {args.model} ...")
    model, cfg, device = load_model(args.model, device=args.device,
                                    batch=args.batch, dtype=args.dtype)
    dim = (model.get_embedding_dimension()
           if hasattr(model, "get_embedding_dimension")
           else model.get_sentence_embedding_dimension())
    print(f"  device={device} dim={dim} batch={cfg.get('batch')}")

    con.execute(f"""
        CREATE OR REPLACE TABLE lobbying_text_embeddings (
          txt_hash TEXT, model TEXT, dim INTEGER, vector FLOAT[{dim}])""")

    t0, done = time.time(), 0
    for i in range(0, len(distinct), args.batch_flush):
        chunk = distinct[i:i + args.batch_flush]
        vecs = encode(model, cfg, [t for _, t in chunk])
        if np.isnan(vecs).any():
            sys.exit("NaN embeddings detected — wrong dtype for this model/GPU "
                     "(Gemma needs fp32 on cards without bf16). Aborting.")
        # Arrow fixed-size lists insert ~30x faster than executemany-ing
        # 768-float python lists row by row.
        import pyarrow as pa
        arrow_chunk = pa.table({
            "txt_hash": pa.array([h for h, _ in chunk]),
            "model": pa.array([args.model] * len(chunk)),
            "dim": pa.array([dim] * len(chunk), type=pa.int32()),
            "vector": pa.FixedSizeListArray.from_arrays(
                pa.array(vecs.astype(np.float32).ravel(), type=pa.float32()), dim),
        })
        con.execute("INSERT INTO lobbying_text_embeddings SELECT * FROM arrow_chunk")
        done += len(chunk)
        rate = done / (time.time() - t0)
        eta = (len(distinct) - done) / rate if rate else 0
        print(f"  {done:,}/{len(distinct):,} ({rate:,.0f} texts/s, ~{eta/60:.0f} min left)")

    n = con.execute("SELECT count(*) FROM lobbying_text_embeddings").fetchone()[0]
    print(f"Done: {n:,} embeddings ({args.model}, dim {dim}) in "
          f"{(time.time()-t0)/60:.1f} min -> {args.db}")
    con.close()


if __name__ == "__main__":
    main()
