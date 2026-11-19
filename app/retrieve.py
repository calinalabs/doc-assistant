"""Hybrid search: keyword (BM25) and meaning (embeddings), merged with reciprocal rank fusion.

Keyword search finds exact things people type (policy numbers, insurer names, clause titles);
embeddings find passages that say the same thing in different words. Fusion keeps the best of both.
"""
import collections
import math
import re

import numpy as np

TOKEN = re.compile(r"[a-z0-9_£%.-]+")


def tokens(text):
    return [t.strip(".-") for t in TOKEN.findall(text.lower()) if t.strip(".-")]


class BM25:
    def __init__(self, texts, k1=1.5, b=0.75):
        self.docs = [collections.Counter(tokens(t)) for t in texts]
        self.lens = [sum(d.values()) for d in self.docs]
        self.avg = (sum(self.lens) / len(self.lens)) if self.lens else 1.0
        df = collections.Counter(w for d in self.docs for w in d)
        n = len(self.docs)
        self.idf = {w: math.log(1 + (n - f + 0.5) / (f + 0.5)) for w, f in df.items()}
        self.k1, self.b = k1, b

    def scores(self, query):
        q = tokens(query)
        out = []
        for d, ln in zip(self.docs, self.lens):
            s = 0.0
            for w in q:
                tf = d.get(w)
                if tf:
                    s += self.idf[w] * tf * (self.k1 + 1) / (tf + self.k1 * (1 - self.b + self.b * ln / self.avg))
            out.append(s)
        return out


def rrf(*rankings, c=60):
    score = collections.defaultdict(float)
    for order in rankings:
        for pos, i in enumerate(order):
            score[i] += 1 / (c + pos + 1)
    return [i for _, i in sorted(((s, i) for i, s in score.items()), reverse=True)]


class Retriever:
    def __init__(self, passages, matrix, embedder, candidates=20):
        from app.index import embed_text
        self.passages, self.matrix, self.embedder, self.candidates = passages, matrix, embedder, candidates
        self.bm25 = BM25([embed_text(p["file"], p["ref"], p["text"]) for p in passages])

    def search_ranked(self, query):
        """Full rankings (passage indices) from each method, used by search() and by the evaluation."""
        kw = self.bm25.scores(query)
        keyword = [i for i in sorted(range(len(kw)), key=lambda i: -kw[i]) if kw[i] > 0]
        qv = np.asarray(self.embedder.embed([query], kind="query")[0], dtype=np.float32)
        embedding = [int(i) for i in np.argsort(-(self.matrix @ qv))]
        hybrid = rrf(keyword[:self.candidates], embedding[:self.candidates])
        return {"keyword": keyword, "embedding": embedding, "hybrid": hybrid}

    def search(self, query, k=6):
        if not self.passages:
            return []
        return [self.passages[i] for i in self.search_ranked(query)["hybrid"][:k]]
