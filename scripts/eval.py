"""Measure the assistant on the test set before anyone relies on it.

Retrieval: does the right passage appear in the top k? (recall@k, MRR of the first right passage)
Answers:   a stronger model judges each answer against the reference; unanswerable questions must be refused.

    uv run scripts/eval.py                     # retrieval + answers (needs API keys)
    uv run scripts/eval.py --retrieval-only    # embeddings only
    uv run scripts/eval.py --fake              # offline dry run
"""
import argparse
import concurrent.futures as cf
import json
import pathlib
import re
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import answer as answering  # noqa: E402
from app import config, index, llm  # noqa: E402
from app.retrieve import Retriever, rrf  # noqa: E402

JUDGE = """You are checking an internal assistant's answer for an insurance broker.

Question: {q}
Reference answer: {ref}
Assistant's answer: {got}

Mark it correct if it gives the same key facts as the reference (figures, conditions, who/when), even in different words,
and says nothing that contradicts the reference. Missing a minor detail is fine; a wrong figure or a missing key condition is not.
Explain in one sentence, then end with <correct>true</correct> or <correct>false</correct>."""


def hit(p, item):
    norm = lambda s: re.sub(r"\s+", " ", s)
    return p["file"].endswith(item["file"]) and norm(item["evidence"]) in norm(p["text"])


def refused(text):
    """A refusal is an answer that is only the not-found reply, not one that flags a missing detail."""
    return text.strip().lower().startswith(answering.NOT_FOUND.lower().rstrip("."))


def retrieval_scores(retriever, items, k, mode):
    rows = []
    for it in items:
        if mode == "hybrid":
            got = retriever.search(it["q"], k=k)
        else:
            full = retriever.search_ranked(it["q"])[mode]
            got = [retriever.passages[i] for i in full[:k]]
        rank = next((n for n, p in enumerate(got, 1) if hit(p, it)), None)
        rows.append(rank)
    n = len(rows)
    return {"recall": sum(r is not None for r in rows) / n, "mrr": sum(1 / r for r in rows if r) / n}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=config.TOP_K)
    ap.add_argument("--retrieval-only", action="store_true")
    ap.add_argument("--fake", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "results"))
    a = ap.parse_args()

    items = json.loads((ROOT / "eval" / "questions.json").read_text())
    answerable = [it for it in items if it["file"]]
    db = index.connect(config.DATA_DIR / "index.db")
    passages, matrix = index.load_passages(db)
    if not passages:
        sys.exit("index is empty: run scripts/ingest.py first")
    embedder = llm.FakeEmbed() if a.fake else llm.embed_client()
    retriever = Retriever(passages, matrix, embedder)

    # retrieval: keyword only, embeddings only, hybrid
    report = {"k": a.k, "questions": len(items), "answerable": len(answerable), "passages": len(passages),
              "embed_model": getattr(embedder, "model", "fake"), "retrieval": {}}
    for mode in ("keyword", "embedding", "hybrid"):
        report["retrieval"][mode] = retrieval_scores(retriever, answerable, a.k, mode)
    print(json.dumps(report["retrieval"], indent=2))

    if not a.retrieval_only:
        chat = llm.FakeChat() if a.fake else llm.chat_client()
        judge = llm.FakeChat() if a.fake else llm.chat_client("anthropic", config.JUDGE_MODEL)

        def run(it):
            t0 = time.time()
            res = answering.answer(it["q"], retriever, chat, k=a.k)
            row = {"q": it["q"], "answer": res["answer"], "cited": [f"{s['file']} | {s['ref']}" for s in res["sources"]],
                   "ms": int((time.time() - t0) * 1000), "usage": res["usage"]}
            if it["file"]:
                verdict, _ = judge.chat("You grade answers strictly and briefly.",
                                        JUDGE.format(q=it["q"], ref=it["answer"], got=res["answer"]), 1500)
                m = re.findall(r"<correct>\s*(true|false)\s*</correct>", verdict, re.I)
                row["correct"] = bool(m) and m[-1].lower() == "true"
                row["judge"] = verdict.strip()
                row["cites_right_file"] = any(s["file"].endswith(it["file"]) for s in res["sources"])
            else:
                row["correct"] = refused(res["answer"])
            return row

        with cf.ThreadPoolExecutor(4) as ex:
            rows = list(ex.map(run, items))
        ans = [r for r, it in zip(rows, items) if it["file"]]
        unans = [r for r, it in zip(rows, items) if not it["file"]]
        report["answers"] = {
            "model": getattr(chat, "model", "fake"),
            "accuracy": sum(r["correct"] for r in ans) / len(ans),
            "cites_right_file": sum(r["cites_right_file"] for r in ans) / len(ans),
            "refusal_accuracy": sum(r["correct"] for r in unans) / len(unans) if unans else None,
            "false_refusals": sum(refused(r["answer"]) for r in ans),
            "avg_ms": sum(r["ms"] for r in rows) / len(rows),
            "input_tokens": sum(r["usage"].get("input", 0) for r in rows),
            "output_tokens": sum(r["usage"].get("output", 0) for r in rows),
        }
        print(json.dumps(report["answers"], indent=2))
        out = pathlib.Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "answers.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False))

    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "eval.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
