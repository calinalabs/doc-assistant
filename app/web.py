"""Web app: sign in, ask a question, get an answer with clickable sources.

Demo sign-in uses an allowlist from USERS. In production this is replaced by the firm's
Google Workspace or Microsoft 365 sign-in, so staff need no extra passwords or ChatGPT licences.
"""
import hmac
import time

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from itsdangerous import BadSignature, URLSafeTimedSerializer
from pydantic import BaseModel

from app import answer as answering
from app import config, index, llm
from app.retrieve import Retriever

SESSION_HOURS = 12
STATIC = config.ROOT / "app" / "static"


def users():
    out = {}
    for pair in config.env("USERS", "demo@broker.example:demo").split(","):
        if ":" in pair:
            u, p = pair.split(":", 1)
            out[u.strip().lower()] = p.strip()
    return out


class State:
    """Index and model clients, created once. reload() picks up a fresh sync."""
    def __init__(self, embedder=None, chat=None, db_path=None):
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.db = index.connect(db_path or config.DATA_DIR / "index.db")
        self.embedder = embedder or llm.embed_client()
        self.chat = chat or llm.chat_client()
        self.reload()

    def reload(self):
        passages, matrix = index.load_passages(self.db)
        self.by_id = {p["id"]: p for p in passages}
        self.retriever = Retriever(passages, matrix, self.embedder)


def create_app(state=None):
    app = FastAPI(title="Calina Labs document assistant", docs_url=None, redoc_url=None)
    signer = URLSafeTimedSerializer(config.env("SESSION_SECRET", "change-me-outside-a-demo"), salt="session")
    holder = {"state": state}

    def st():
        if holder["state"] is None:
            holder["state"] = State()
        return holder["state"]

    def current_user(request: Request):
        token = request.cookies.get("session")
        try:
            return signer.loads(token, max_age=SESSION_HOURS * 3600) if token else None
        except BadSignature:
            return None

    def require_user(request: Request):
        user = current_user(request)
        if not user:
            raise HTTPException(401, "Sign in first")
        return user

    @app.get("/")
    def home(request: Request):
        if not current_user(request):
            return RedirectResponse("/login")
        return FileResponse(STATIC / "index.html")

    @app.get("/login")
    def login_page():
        return FileResponse(STATIC / "login.html")

    @app.post("/login")
    def login(email: str = Form(...), password: str = Form(...)):
        expected = users().get(email.strip().lower())
        if expected is None or not hmac.compare_digest(expected, password):
            time.sleep(0.5)
            return RedirectResponse("/login?error=1", status_code=303)
        resp = RedirectResponse("/", status_code=303)
        resp.set_cookie("session", signer.dumps(email.strip().lower()), httponly=True, samesite="lax",
                        secure=config.env("COOKIE_SECURE", "0") == "1", max_age=SESSION_HOURS * 3600)
        return resp

    @app.post("/logout")
    def logout():
        resp = RedirectResponse("/login", status_code=303)
        resp.delete_cookie("session")
        return resp

    class Ask(BaseModel):
        question: str

    @app.post("/api/ask")
    def ask(body: Ask, user: str = Depends(require_user)):
        q = body.question.strip()[:2000]
        if not q:
            raise HTTPException(400, "Empty question")
        s, t0 = st(), time.time()
        res = answering.answer(q, s.retriever, s.chat)
        ms = int((time.time() - t0) * 1000)
        index.log_question(s.db, user, q, res["answer"], res["sources"], res["usage"], ms,
                           getattr(s.chat, "model", "fake"))
        return {"answer": res["answer"], "ms": ms,
                "sources": [{"n": p["n"], "id": p["id"], "file": p["file"], "ref": p["ref"]} for p in res["sources"]]}

    @app.get("/api/source/{pid}")
    def source(pid: int, user: str = Depends(require_user)):
        p = st().by_id.get(pid)
        if not p:
            raise HTTPException(404, "Not found")
        return {"file": p["file"], "ref": p["ref"], "text": p["text"]}

    @app.get("/api/me")
    def me(user: str = Depends(require_user)):
        s = st()
        files = s.db.execute("select count(*) from files").fetchone()[0]
        return {"user": user, "files": files, "passages": len(s.by_id), "model": getattr(s.chat, "model", "fake")}

    @app.get("/static/{name}")
    def static(name: str):
        f = (STATIC / name).resolve()
        if f.parent != STATIC.resolve() or not f.exists():
            raise HTTPException(404)
        return FileResponse(f)

    @app.exception_handler(401)
    def unauthorised(request: Request, exc):
        return JSONResponse({"detail": "Sign in first"}, status_code=401)

    return app


app = create_app()
