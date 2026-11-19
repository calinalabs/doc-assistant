"""Settings, all from environment variables (or ~/.config/calinalabs/keys.env for API keys).

PROVIDER        chat model provider: openai | anthropic | gemini   (default: anthropic)
EMBED_PROVIDER  embedding provider: openai | gemini                (default: gemini)
OPENAI_MODEL, ANTHROPIC_MODEL, GEMINI_MODEL, OPENAI_EMBED_MODEL, GEMINI_EMBED_MODEL
DATA_DIR        where the index and caches live                     (default: ./data)
USERS           demo logins, "alice@broker.example:pass,bob@broker.example:pass"
SESSION_SECRET  cookie signing key (set a long random value outside a demo)
TOP_K           passages given to the model                         (default: 6)
"""
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def load_keys():
    """Read KEY=value lines from ~/.config/calinalabs/keys.env without overriding the environment."""
    f = pathlib.Path.home() / ".config" / "calinalabs" / "keys.env"
    if f.exists():
        for line in f.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_keys()


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


PROVIDER = env("PROVIDER", "anthropic")
EMBED_PROVIDER = env("EMBED_PROVIDER", "gemini")
MODELS = {
    "openai": env("OPENAI_MODEL", "gpt-4.1-mini"),
    "anthropic": env("ANTHROPIC_MODEL", "claude-haiku-5-5"),
    "gemini": env("GEMINI_MODEL", "gemini-2.5-flash"),
}
EMBED_MODELS = {
    "openai": env("OPENAI_EMBED_MODEL", "text-embedding-3-small"),
    "gemini": env("GEMINI_EMBED_MODEL", "gemini-embedding-2"),
}
JUDGE_MODEL = env("JUDGE_MODEL", "claude-sonnet-5-5")
DATA_DIR = pathlib.Path(env("DATA_DIR", str(ROOT / "data")))
INSTRUCTIONS = pathlib.Path(env("INSTRUCTIONS", str(ROOT / "instructions.md")))
TOP_K = int(env("TOP_K", "6"))
