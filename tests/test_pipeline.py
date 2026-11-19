"""Offline tests: fake embeddings and a fake model, real files, real index and web app."""
import json
import pathlib
import shutil
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import answer as answering, index, llm  # noqa: E402
from app.extract import extract  # noqa: E402
from app.retrieve import Retriever, rrf  # noqa: E402
from app.sources import LocalFolderSource  # noqa: E402


@pytest.fixture(scope="session")
def demo(tmp_path_factory):
    out = tmp_path_factory.mktemp("demo")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "make_demo_docs.py"), str(out)], check=True, cwd=ROOT)
    return out


@pytest.fixture
def db(tmp_path, demo):
    d = index.connect(tmp_path / "index.db")
    index.sync(d, LocalFolderSource(demo), llm.FakeEmbed(), log=lambda *_: None)
    return d


def test_extract_every_format(demo):
    pdf = extract(demo / "Policy wordings" / "Harbourline Commercial Property Policy Wording.pdf")
    assert [p["ref"] for p in pdf][:3] == ["p. 1", "p. 2", "p. 3"]
    assert any("Escape of water: £1,000" in p["text"] for p in pdf)
    guide = extract(demo / "Placement and Underwriting Guide.docx")
    assert any(p["ref"] == "§ Authority levels" for p in guide)
    assert any(p["ref"] == "table 1" and "Fleet motor" in p["text"] for p in guide)
    sheet = extract(demo / "Insurer rates and appetite.xlsx")
    assert any(p["ref"].startswith("Sheet Rates, rows 2-") and "£2,150 per vehicle" in p["text"] for p in sheet)
    mail = extract(next((demo / "Insurer emails").glob("*Kestrel*.eml")))
    assert mail[0]["ref"] == "email" and "7.5%" in mail[0]["text"] and "From: Priya Shah" in mail[0]["text"]


def test_sync_is_incremental(tmp_path, demo):
    folder = tmp_path / "docs"
    shutil.copytree(demo, folder)
    d = index.connect(tmp_path / "i.db")
    quiet = lambda *_: None
    first = index.sync(d, LocalFolderSource(folder), llm.FakeEmbed(), log=quiet)
    assert first["added"] == 9
    assert index.sync(d, LocalFolderSource(folder), llm.FakeEmbed(), log=quiet)["unchanged"] == 9
    (folder / "Insurer emails" / "2026-09-18 Harbourline - escape of water excess change.eml").unlink()
    (folder / "note.txt").write_text("Office closes at 5pm on Fridays.")
    third = index.sync(d, LocalFolderSource(folder), llm.FakeEmbed(), log=quiet)
    assert third["removed"] == 1 and third["added"] == 1
    texts = [r[0] for r in d.execute("select text from passages")]
    assert not any("increase from £1,000 to £2,500" in t for t in texts)


def test_rrf_prefers_items_ranked_well_by_both():
    assert rrf([1, 2, 3], [2, 3, 1])[0] == 2


def test_hybrid_finds_exact_figures(db):
    passages, matrix = index.load_passages(db)
    r = Retriever(passages, matrix, llm.FakeEmbed())
    top = r.search("Ashby & Vale charge per HGV minimum premium", k=3)
    assert any("£2,150 per vehicle" in p["text"] for p in top)


def test_answer_maps_citations(db):
    passages, matrix = index.load_passages(db)
    res = answering.answer("escape of water excess Harbourline", Retriever(passages, matrix, llm.FakeEmbed()), llm.FakeChat())
    assert res["sources"] and res["sources"][0]["n"] == 1
    assert answering.cited("x [S2] y [S9] [S2]", [{"id": 1}, {"id": 2}]) == [{"n": 2, "id": 2}]


def test_empty_index_refuses(tmp_path):
    d = index.connect(tmp_path / "empty.db")
    passages, matrix = index.load_passages(d)
    res = answering.answer("anything", Retriever(passages, matrix, llm.FakeEmbed()), llm.FakeChat())
    assert res["answer"] == answering.NOT_FOUND


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.setenv("USERS", "alice@broker.example:secret")
    from app import web
    state = web.State.__new__(web.State)
    state.db, state.embedder, state.chat = db, llm.FakeEmbed(), llm.FakeChat()
    state.reload()
    return TestClient(web.create_app(state))


def test_requires_sign_in(client):
    assert client.post("/api/ask", json={"question": "hi"}).status_code == 401
    assert client.get("/api/source/1").status_code == 401
    assert client.get("/", follow_redirects=False).headers["location"] == "/login"


def test_wrong_password_rejected(client):
    r = client.post("/login", data={"email": "alice@broker.example", "password": "nope"}, follow_redirects=False)
    assert "error" in r.headers["location"] and "session" not in r.cookies


def test_ask_and_audit_log_has_no_document_text(client, db):
    client.post("/login", data={"email": "alice@broker.example", "password": "secret"})
    r = client.post("/api/ask", json={"question": "What is the escape of water excess with Harbourline?"})
    assert r.status_code == 200
    body = r.json()
    assert body["sources"] and {"file", "ref", "id"} <= set(body["sources"][0])
    src = client.get(f"/api/source/{body['sources'][0]['id']}").json()
    assert src["text"]
    user, sources = db.execute("select user, sources from audit").fetchone()
    assert user == "alice@broker.example" and json.loads(sources)
    row = " ".join(str(c) for c in db.execute("select * from audit").fetchone())
    assert src["text"] not in row  # cited passage ids are logged, not whole passages


def test_static_path_traversal_blocked(client):
    assert client.get("/static/..%2F..%2Fpyproject.toml").status_code == 404
