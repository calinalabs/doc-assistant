"""Model clients over plain HTTPS (no SDKs): chat and embeddings for OpenAI, Anthropic and Gemini.

Every chat client returns (text, usage) where usage = {"input": n, "output": n}.
Fake clients make the whole pipeline testable offline.
"""
import hashlib
import json
import math
import os
import pathlib
import random
import re
import time
import urllib.error
import urllib.request

from app import config


def post(url, body, headers, tries=8):
    """POST JSON with retry on rate limits and transient errors."""
    data = json.dumps(body).encode()
    for attempt in range(tries):
        req = urllib.request.Request(url, data=data, headers={"content-type": "application/json", **headers})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            detail = e.read()
            if e.code in (429, 500, 502, 503, 529) and attempt < tries - 1:
                m = re.search(rb'"retryDelay":\s*"(\d+(?:\.\d+)?)s"', detail)
                time.sleep(float(m.group(1)) + 1 if m else min(30, 2 ** attempt) + random.random())
                continue
            raise RuntimeError(f"{url.split('?')[0]} -> HTTP {e.code}: {detail[:300]!r}") from None
        except urllib.error.URLError:
            if attempt < tries - 1:
                time.sleep(2 ** attempt)
                continue
            raise
    raise RuntimeError("unreachable")


def normalise(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


# ------------------------------------------------------------------ chat

class OpenAIChat:
    def __init__(self, model=None):
        self.key, self.model = os.environ["OPENAI_API_KEY"], model or config.MODELS["openai"]

    def chat(self, system, user, max_tokens=1200):
        res = post("https://api.openai.com/v1/chat/completions",
                   {"model": self.model, "max_tokens": max_tokens, "temperature": 0,
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]},
                   {"authorization": f"Bearer {self.key}"})
        u = res.get("usage", {})
        return res["choices"][0]["message"]["content"], {"input": u.get("prompt_tokens", 0), "output": u.get("completion_tokens", 0)}


class AnthropicChat:
    def __init__(self, model=None):
        self.key, self.model = os.environ["ANTHROPIC_API_KEY"], model or config.MODELS["anthropic"]

    def chat(self, system, user, max_tokens=1200):
        res = post("https://api.anthropic.com/v1/messages",
                   {"model": self.model, "max_tokens": max_tokens, "system": system,
                    "messages": [{"role": "user", "content": user}]},
                   {"x-api-key": self.key, "anthropic-version": "2023-06-01"})
        u = res.get("usage", {})
        return "".join(b.get("text", "") for b in res["content"]), {"input": u.get("input_tokens", 0), "output": u.get("output_tokens", 0)}


class GeminiChat:
    def __init__(self, model=None):
        self.key, self.model = os.environ["GEMINI_API_KEY"], model or config.MODELS["gemini"]

    def chat(self, system, user, max_tokens=1200):
        res = post(f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
                   {"systemInstruction": {"parts": [{"text": system}]},
                    "contents": [{"role": "user", "parts": [{"text": user}]}],
                    "generationConfig": {"temperature": 0, "maxOutputTokens": max_tokens}},
                   {"x-goog-api-key": self.key})
        parts = res["candidates"][0].get("content", {}).get("parts", [])
        u = res.get("usageMetadata", {})
        return "".join(p.get("text", "") for p in parts), {"input": u.get("promptTokenCount", 0), "output": u.get("candidatesTokenCount", 0)}


CHAT = {"openai": OpenAIChat, "anthropic": AnthropicChat, "gemini": GeminiChat}


def chat_client(provider=None, model=None):
    return CHAT[provider or config.PROVIDER](model)


# ------------------------------------------------------------- embeddings

class _CachedEmbed:
    """Caches each vector on disk by (model, text) hash, so re-indexing unchanged text is free."""
    batch = 16

    def __init__(self, model, cache_dir=None):
        self.model = model
        self.cache = pathlib.Path(cache_dir or config.DATA_DIR / ".embed-cache")
        self.cache.mkdir(parents=True, exist_ok=True)

    def embed(self, texts, kind="document"):
        out, todo = [None] * len(texts), []
        for i, t in enumerate(texts):
            p = self.cache / (hashlib.sha256(f"{self.model}|{kind}|{t}".encode()).hexdigest() + ".json")
            if p.exists():
                out[i] = json.loads(p.read_text())
            else:
                todo.append((i, t, p))
        for s in range(0, len(todo), self.batch):
            chunk = todo[s:s + self.batch]
            for (i, _, p), v in zip(chunk, self._call([t for _, t, _ in chunk], kind)):
                v = normalise(v)
                p.write_text(json.dumps(v))
                out[i] = v
        return out


class GeminiEmbed(_CachedEmbed):
    batch = 8

    def __init__(self, cache_dir=None):
        super().__init__(config.EMBED_MODELS["gemini"], cache_dir)
        self.key = os.environ["GEMINI_API_KEY"]

    def _call(self, texts, kind):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:batchEmbedContents"
        body = {"requests": [{"model": f"models/{self.model}", "content": {"parts": [{"text": t}]}} for t in texts]}
        return [e["values"] for e in post(url, body, {"x-goog-api-key": self.key})["embeddings"]]


class OpenAIEmbed(_CachedEmbed):
    batch = 64

    def __init__(self, cache_dir=None):
        super().__init__(config.EMBED_MODELS["openai"], cache_dir)
        self.key = os.environ["OPENAI_API_KEY"]

    def _call(self, texts, kind):
        res = post("https://api.openai.com/v1/embeddings", {"model": self.model, "input": texts},
                   {"authorization": f"Bearer {self.key}"})
        return [d["embedding"] for d in sorted(res["data"], key=lambda d: d["index"])]


EMBED = {"gemini": GeminiEmbed, "openai": OpenAIEmbed}


def embed_client(provider=None):
    return EMBED[provider or config.EMBED_PROVIDER]()


# ---------------------------------------------------------------- fakes

class FakeEmbed:
    """Deterministic bag-of-words vectors, so tests and dry runs need no API."""
    model = "fake"

    def embed(self, texts, kind="document"):
        out = []
        for t in texts:
            v = [0.0] * 256
            for w in re.findall(r"[a-z0-9]{3,}", t.lower()):
                v[int(hashlib.md5(w.encode()).hexdigest(), 16) % 256] += 1
            out.append(normalise(v))
        return out


class FakeChat:
    """Answers by quoting the first source, or says it can't find the answer if there are none."""
    def chat(self, system, user, max_tokens=0):
        if "<correct>" in user or "<correct>" in system:
            return "<correct>true</correct>", {"input": 0, "output": 0}
        if "[S1]" not in user:
            return "I can't find this in the documents.", {"input": 0, "output": 0}
        m = re.search(r"\[S1\][^\n]*\n(.{0,160})", user, re.S)
        return f"{(m.group(1) if m else '').strip()} [S1]", {"input": 10, "output": 5}
