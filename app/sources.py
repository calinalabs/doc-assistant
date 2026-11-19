"""Where documents come from. Each source lists files as (file_id, name, version) and can download one.

LocalFolderSource   a folder on disk (demo and tests)
GoogleDriveSource   one Drive folder and its subfolders, read-only, via a service account.
                    Staff never need Drive access: only the service account can read the folder.
"""
import hashlib
import pathlib

from app.extract import supported


class LocalFolderSource:
    def __init__(self, folder):
        self.folder = pathlib.Path(folder)

    def list(self):
        for p in sorted(self.folder.rglob("*")):
            if p.is_file() and supported(p) and not p.name.startswith((".", "~$")):
                rel = str(p.relative_to(self.folder))
                yield rel, rel, hashlib.sha256(p.read_bytes()).hexdigest()

    def fetch(self, file_id, dest_dir):
        return self.folder / file_id


class GoogleDriveSource:
    """Needs the optional extra: uv sync --extra drive. Share the folder with the service account's email."""
    EXPORT = {
        "application/vnd.google-apps.document": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx"),
        "application/vnd.google-apps.spreadsheet": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"),
    }

    def __init__(self, folder_id, credentials_file):
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        creds = service_account.Credentials.from_service_account_file(
            credentials_file, scopes=["https://www.googleapis.com/auth/drive.readonly"])
        self.drive = build("drive", "v3", credentials=creds, cache_discovery=False)
        self.folder_id = folder_id
        self._names = {}

    def _walk(self, folder_id, prefix=""):
        token = None
        while True:
            res = self.drive.files().list(
                q=f"'{folder_id}' in parents and trashed = false",
                fields="nextPageToken, files(id, name, mimeType, modifiedTime, md5Checksum)",
                pageToken=token, supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
            for f in res.get("files", []):
                if f["mimeType"] == "application/vnd.google-apps.folder":
                    yield from self._walk(f["id"], f"{prefix}{f['name']}/")
                    continue
                name = prefix + f["name"]
                if f["mimeType"] in self.EXPORT:
                    name += self.EXPORT[f["mimeType"]][1]
                elif not supported(name):
                    continue
                self._names[f["id"]] = (name, f["mimeType"])
                yield f["id"], name, f.get("md5Checksum") or f["modifiedTime"]
            token = res.get("nextPageToken")
            if not token:
                return

    def list(self):
        yield from self._walk(self.folder_id)

    def fetch(self, file_id, dest_dir):
        from googleapiclient.http import MediaIoBaseDownload
        name, mime = self._names[file_id]
        dest = pathlib.Path(dest_dir) / file_id
        dest.mkdir(parents=True, exist_ok=True)
        out = dest / pathlib.Path(name).name
        req = (self.drive.files().export_media(fileId=file_id, mimeType=self.EXPORT[mime][0]) if mime in self.EXPORT
               else self.drive.files().get_media(fileId=file_id, supportsAllDrives=True))
        with open(out, "wb") as fh:
            dl = MediaIoBaseDownload(fh, req)
            done = False
            while not done:
                _, done = dl.next_chunk()
        return out
