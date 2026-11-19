# Calina Labs: private document assistant

A secure internal assistant that answers staff questions from a firm's own documents (PDF, Word, Excel and saved emails) and cites the file and page, section, sheet rows or email for every answer. If the documents don't answer a question, it says so instead of guessing.

This is a reference build by [Calina Labs](https://calinalabs.com), shown on a fictional insurance broker. All firms, insurers, clients and figures in the demo documents are invented.

- Write-up: [Building a document assistant for an insurance broker, measured on 46 questions](https://calinalabs.com/blog/document-assistant-insurance-broker/)
- Related: [RAG evaluation](https://calinalabs.com/blog/rag-evaluation/) · [Gemini Embedding RAG experiment](https://calinalabs.com/blog/gemini-embedding-rag/) · [calinalabs/rag](https://github.com/calinalabs/rag)

## What it does

| Need | How |
|---|---|
| Answer from the firm's documents only | Hybrid search (keyword BM25 + embeddings, merged with reciprocal rank fusion), then the model answers from the numbered passages only |
| A source for every answer | Each passage keeps its file and location (`p. 3`, `§ Authority levels`, `Sheet Rates, rows 2-12`, `email`); answers cite `[S1]`, and the chat opens the cited passage |
| "Not in the documents" | The model must reply "I can't find this in the documents." when the sources don't answer; tested with unanswerable questions |
| Reuse existing assistant instructions | `instructions.md` is the house prompt (e.g. pasted ChatGPT plugin instructions), editable without code |
| Staff need no Drive access | A read-only Google service account syncs the folder; staff only see answers and cited passages |
| No individual ChatGPT licences | One API key on the server; staff sign in to the web app (demo: allowlist; production: Google Workspace or Microsoft 365 sign-in) |
| Audit | Every question is logged with the user, answer, cited passage IDs, tokens and time, but not document text |
| Any model | `PROVIDER=openai`, `anthropic` or `gemini`; `EMBED_PROVIDER=openai` or `gemini` |
| Kept up to date | `ingest.py` re-reads only new or changed files and removes deleted ones |

## Results on the demo set

46 questions: 40 answerable (each with the file and the passage that answers it) and 6 unanswerable. Top 6 passages per question. Embeddings: Gemini Embedding 2. Answers: Claude Haiku 5.5. Judge: Claude Sonnet 5.5.

| Retrieval (40 answerable questions) | Right passage in top 6 | MRR |
|---|---|---|
| Keyword only (BM25) | 0.975 | 0.91 |
| Embeddings only | 1.00 | 0.95 |
| **Hybrid** | **1.00** | **0.99** |

| Answers | Result |
|---|---|
| Correct (judged against the reference) | 38 / 40 (95%) |
| Cites the file that holds the answer | 40 / 40 |
| Unanswerable questions refused | 6 / 6 |
| Answerable questions wrongly refused | 0 |
| Average response time | about 3 s |

The demo set is small (29 passages), so retrieval is easy here. On a real document folder with thousands of passages, the same test set approach is what shows where it breaks. The two misses are kept in the results: one answer left out "we notify the insurer the same working day", and one added a stricter reading of the 10% renewal rule. Every answer is in `results/answers.json` after a run; summary numbers are in `results/eval.json`.

## Run it

```bash
git clone https://github.com/calinalabs/doc-assistant && cd doc-assistant
uv sync
# keys: env vars, or ~/.config/calinalabs/keys.env with GEMINI_API_KEY=..., ANTHROPIC_API_KEY=... (or OPENAI_API_KEY=...)
uv run scripts/make_demo_docs.py              # fictional broker documents into data/demo
uv run scripts/ingest.py data/demo            # build the index (re-run any time; only changes are re-read)
uv run scripts/eval.py                        # measure retrieval and answers on eval/questions.json
USERS="you@firm.example:choose-a-password" SESSION_SECRET="long-random-string" \
  uv run uvicorn app.web:app --port 8040     # then open http://127.0.0.1:8040
uv run pytest                                 # offline tests, no API keys needed
```

Google Drive instead of a local folder:

```bash
uv sync --extra drive
uv run scripts/ingest.py --drive <FOLDER_ID> --credentials service-account.json
```

Share the Drive folder with the service account's email (viewer). Google Docs and Sheets are exported as Word and Excel.

To use OpenAI: `PROVIDER=openai EMBED_PROVIDER=openai OPENAI_API_KEY=...` (models set by `OPENAI_MODEL`, `OPENAI_EMBED_MODEL`).

## Layout

```
app/extract.py    PDF / Word / Excel / .eml / .msg -> passages with page, section, sheet rows
app/sources.py    local folder or Google Drive (read-only service account)
app/index.py      SQLite index, incremental sync, audit log
app/retrieve.py   BM25 + embeddings + reciprocal rank fusion
app/answer.py     prompt with numbered sources, citation mapping, not-found rule
app/llm.py        OpenAI / Anthropic / Gemini over plain HTTPS, with retries and an embedding cache
app/web.py        FastAPI app: sign-in, ask, open a cited passage
scripts/          demo documents, ingest, evaluation
eval/             test questions with the expected file and passage
```

## Before using it with real documents

- Replace the demo sign-in with the firm's Google Workspace or Microsoft 365 sign-in, and set `SESSION_SECRET` and `COOKIE_SECURE=1` behind HTTPS.
- Host in a UK region; use an API account where the provider does not train on your data, and check the data processing terms.
- Build the test set from 30–100 real staff questions, and run `scripts/eval.py` after every change to documents, prompts or models.

---

Built by [Calina Labs](https://calinalabs.com), a London AI engineering studio. Want this on your own documents? [Get in touch](https://calinalabs.com/contact/).
