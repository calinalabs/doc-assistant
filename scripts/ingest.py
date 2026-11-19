"""Sync documents into the index. Only new or changed files are re-read; deleted files are removed.

    uv run scripts/ingest.py data/demo                                  # a local folder
    uv run scripts/ingest.py --drive FOLDER_ID --credentials sa.json     # a Google Drive folder (uv sync --extra drive)
"""
import argparse
import sys
import time

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

from app import config, index, llm  # noqa: E402
from app.sources import GoogleDriveSource, LocalFolderSource  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", nargs="?")
    ap.add_argument("--drive", help="Google Drive folder ID")
    ap.add_argument("--credentials", help="service account JSON file")
    ap.add_argument("--fake", action="store_true", help="offline embeddings (testing only)")
    a = ap.parse_args()
    if a.drive:
        source = GoogleDriveSource(a.drive, a.credentials)
    elif a.folder:
        source = LocalFolderSource(a.folder)
    else:
        ap.error("give a folder or --drive")
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    db = index.connect(config.DATA_DIR / "index.db")
    t0 = time.time()
    stats = index.sync(db, source, llm.FakeEmbed() if a.fake else llm.embed_client())
    n = db.execute("select count(*) from passages").fetchone()[0]
    print(f"{stats} -> {n} passages in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
