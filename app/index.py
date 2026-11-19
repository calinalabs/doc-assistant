"""SQLite index: files, passages with their embeddings, and the audit log.

sync() re-indexes only files whose version changed and removes files that disappeared from the source.
"""
import json
import sqlite3
import tempfile
import time

import numpy as np

from app.extract import extract

SCHEMA = """
create table if not exists files (id text primary key, name text, version text, indexed_at real);
create table if not exists passages (
  id integer primary key, file_id text references files(id) on delete cascade,
  file text, ref text, text text, vec blob);
create table if not exists audit (
  id integer primary key, at real, user text, question text, answer text,
  sources text, input_tokens int, output_tokens int, ms int, model text);
"""


def connect(path):
    db = sqlite3.connect(str(path), check_same_thread=False)
    db.execute("pragma foreign_keys = on")
    db.executescript(SCHEMA)
    return db


def embed_text(file, ref, text):
    """What gets embedded: the file and location give context ('Harbourline Commercial Property, p. 4')."""
    return f"{file} | {ref}\n{text}"


def sync(db, source, embedder, log=print):
    """Bring the index in line with the source. Returns counts of added/updated/removed/unchanged files."""
    known = {r[0]: r[1] for r in db.execute("select id, version from files")}
    seen, stats = set(), {"added": 0, "updated": 0, "removed": 0, "unchanged": 0}
    with tempfile.TemporaryDirectory() as tmp:
        for file_id, name, version in source.list():
            seen.add(file_id)
            if known.get(file_id) == version:
                stats["unchanged"] += 1
                continue
            try:
                passages = extract(source.fetch(file_id, tmp))
            except Exception as e:  # one unreadable file must not stop the sync
                log(f"  skipped {name}: {e}")
                continue
            vecs = embedder.embed([embed_text(name, p["ref"], p["text"]) for p in passages]) if passages else []
            db.execute("delete from passages where file_id = ?", (file_id,))
            db.execute("insert or replace into files values (?, ?, ?, ?)", (file_id, name, version, time.time()))
            db.executemany("insert into passages (file_id, file, ref, text, vec) values (?, ?, ?, ?, ?)",
                           [(file_id, name, p["ref"], p["text"], np.asarray(v, dtype=np.float32).tobytes())
                            for p, v in zip(passages, vecs)])
            stats["updated" if file_id in known else "added"] += 1
            log(f"  {'updated' if file_id in known else 'added'} {name} ({len(passages)} passages)")
        for file_id in set(known) - seen:
            db.execute("delete from passages where file_id = ?", (file_id,))
            db.execute("delete from files where id = ?", (file_id,))
            stats["removed"] += 1
    db.commit()
    return stats


def load_passages(db):
    rows = db.execute("select id, file, ref, text, vec from passages order by id").fetchall()
    passages = [{"id": r[0], "file": r[1], "ref": r[2], "text": r[3]} for r in rows]
    matrix = np.vstack([np.frombuffer(r[4], dtype=np.float32) for r in rows]) if rows else np.zeros((0, 1), np.float32)
    return passages, matrix


def log_question(db, user, question, answer, sources, usage, ms, model):
    """The audit log keeps the question, answer and which passages were cited, never the passage text."""
    db.execute("insert into audit (at, user, question, answer, sources, input_tokens, output_tokens, ms, model) "
               "values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
               (time.time(), user, question, answer, json.dumps([s["id"] for s in sources]),
                usage.get("input", 0), usage.get("output", 0), ms, model))
    db.commit()
