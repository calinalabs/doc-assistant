"""Build the prompt from numbered sources, call the model, and map [S1]-style citations back to passages."""
import re

from app import config

RULES = """
How to answer (these rules come before anything else):
- Answer only from the numbered sources provided. Do not use outside knowledge about insurers, policies or law.
- Start with the direct answer in one to three sentences. Then add at most three short bullet points, only for details
  staff need to act on (a condition precedent, a referral, a deadline, a newer email that changes the figure).
- After every statement, cite the source(s) it comes from, like [S1] or [S2][S4].
- Quote figures (limits, excesses, rates, dates) exactly as written in the source.
- If sources disagree (for example a wording and a newer insurer email), give both and say which is newer.
- If the sources do not answer the question at all, reply only: "I can't find this in the documents."
- If they answer part of it, answer that part and say "The documents don't say ..." for the missing part.
""".strip()

NOT_FOUND = "I can't find this in the documents."


def system_prompt():
    house = config.INSTRUCTIONS.read_text().strip() if config.INSTRUCTIONS.exists() else ""
    return f"{house}\n\n{RULES}".strip()


def build_user_prompt(question, passages):
    blocks = [f"[S{n}] {p['file']}, {p['ref']}\n{p['text']}" for n, p in enumerate(passages, 1)]
    return "Sources:\n\n" + "\n\n---\n\n".join(blocks) + f"\n\nQuestion: {question}"


def cited(text, passages):
    """Return the passages actually cited in the answer, in citation order, without duplicates."""
    out, seen = [], set()
    for m in re.finditer(r"\[S(\d+)\]", text):
        n = int(m.group(1))
        if 1 <= n <= len(passages) and n not in seen:
            seen.add(n)
            out.append({"n": n, **passages[n - 1]})
    return out


def answer(question, retriever, llm, k=None):
    passages = retriever.search(question, k=k or config.TOP_K)
    if not passages:
        return {"answer": NOT_FOUND, "sources": [], "retrieved": [], "usage": {}}
    text, usage = llm.chat(system_prompt(), build_user_prompt(question, passages))
    return {"answer": text.strip(), "sources": cited(text, passages),
            "retrieved": [p["id"] for p in passages], "usage": usage}
