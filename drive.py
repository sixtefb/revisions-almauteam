"""Accès Google Drive (lecture + ajout de cours) pour la plateforme.

Deux modes d'authentification (variables d'environnement) :
  1. RECOMMANDÉ — compte du propriétaire du Drive (OAuth, refresh token) :
       GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN
     -> lecture + ajout, les fichiers ajoutés appartiennent au propriétaire du Drive.
  2. Compte de service (GOOGLE_SERVICE_ACCOUNT_JSON, JSON brut ou base64) :
     -> lecture OK ; l'ajout peut être refusé par Google (les comptes de service n'ont pas de quota Drive).
"""
import os
import io
import json
import base64
import threading

ROOT_ID = os.environ.get("DRIVE_ROOT_FOLDER_ID", "1zY3bjuGbQXG7i9UThmIRFhqfl6z42X_Z")
# Sous-dossiers de « ALMA U » -> matière de la plateforme (modifiable via DRIVE_FOLDER_MAP='{"sid":"folderId",...}')
DEFAULT_MAP = {
    "global-marketing": "1RCwTg6TD061XYm5cIMbeBDZHQc7ITOX6",
    "ai-marketing": "1oqQ-JvRFTskRIkO4Z2S0rMUvNOtu0W9-",
    "customer-development": "1znJ50jX0BCGEiMhumtBLlGPQ4pxeU7f5",
    "lodging": "1acS-Z6uSdLuDKiUY1C7ZrysqNcBmeR-y",
}
try:
    FOLDER_MAP = {**DEFAULT_MAP, **json.loads(os.environ.get("DRIVE_FOLDER_MAP", "{}") or "{}")}
except ValueError:
    FOLDER_MAP = dict(DEFAULT_MAP)

FOLDER_MIME = "application/vnd.google-apps.folder"
SCOPES = ["https://www.googleapis.com/auth/drive"]
MAX_UPLOAD = int(os.environ.get("MAX_UPLOAD_MB", "25")) * 1024 * 1024
ALLOWED_EXT = {".pdf", ".pptx", ".ppt", ".docx", ".doc", ".xlsx", ".xls", ".txt", ".md", ".csv",
               ".png", ".jpg", ".jpeg", ".webp", ".heic", ".zip", ".mp3", ".m4a"}
EXPORTS = {  # fichiers Google natifs -> export
    "application/vnd.google-apps.document": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.presentation": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.spreadsheet": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.drawing": ("application/pdf", ".pdf"),
}
FIELDS = "id,name,mimeType,size,modifiedTime,createdTime,parents,description,webViewLink"

_lock = threading.Lock()
_svc = {"obj": None}
FOLDER_SUBJECT = {}      # id de dossier connu -> matière (rempli au fil des listings)


def mode():
    if os.environ.get("GOOGLE_REFRESH_TOKEN") and os.environ.get("GOOGLE_CLIENT_ID") and os.environ.get("GOOGLE_CLIENT_SECRET"):
        return "oauth"
    if os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON"):
        return "service_account"
    return None


def service_account_email():
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    try:
        return json.loads(_decode(raw)).get("client_email")
    except Exception:  # noqa: BLE001
        return None


def _decode(raw):
    raw = raw.strip()
    return raw if raw.startswith("{") else base64.b64decode(raw).decode()


def get_service():
    """Client Drive v3 (créé une fois). Lève RuntimeError si non configuré."""
    with _lock:
        if _svc["obj"] is not None:
            return _svc["obj"]
        m = mode()
        if not m:
            raise RuntimeError("Google Drive n'est pas configuré sur le serveur.")
        from googleapiclient.discovery import build
        if m == "oauth":
            from google.oauth2.credentials import Credentials
            creds = Credentials(None, refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
                                client_id=os.environ["GOOGLE_CLIENT_ID"], client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
                                token_uri="https://oauth2.googleapis.com/token", scopes=SCOPES)
        else:
            from google.oauth2 import service_account
            creds = service_account.Credentials.from_service_account_info(
                json.loads(_decode(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])), scopes=SCOPES)
        _svc["obj"] = build("drive", "v3", credentials=creds, cache_discovery=False)
        return _svc["obj"]


def _q(s):
    return s.replace("\\", "\\\\").replace("'", "\\'")


def list_folder(folder_id, sid):
    """Contenu d'un dossier : sous-dossiers d'abord, puis fichiers (récents en premier)."""
    svc = get_service()
    items, token = [], None
    while True:
        r = svc.files().list(q=f"'{_q(folder_id)}' in parents and trashed = false", fields=f"nextPageToken,files({FIELDS})",
                             pageSize=200, pageToken=token, orderBy="folder,name_natural",
                             supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
        items += r.get("files", [])
        token = r.get("nextPageToken")
        if not token:
            break
    out = []
    for f in items:
        is_dir = f["mimeType"] == FOLDER_MIME
        if is_dir:
            FOLDER_SUBJECT[f["id"]] = sid
        out.append({"id": f["id"], "name": f["name"], "folder": is_dir, "mime": f["mimeType"],
                    "size": int(f["size"]) if f.get("size") else None, "modified": f.get("modifiedTime"),
                    "note": f.get("description") or "", "link": f.get("webViewLink")})
    return out


def owning_subject(file_id):
    """Matière d'un fichier en remontant ses parents (max 6 niveaux) ; None s'il est hors des dossiers de cours."""
    svc = get_service()
    cur, roots = file_id, {v: k for k, v in FOLDER_MAP.items()}
    for _ in range(6):
        if cur in roots:
            return roots[cur]
        if cur in FOLDER_SUBJECT:
            return FOLDER_SUBJECT[cur]
        meta = svc.files().get(fileId=cur, fields="id,parents", supportsAllDrives=True).execute()
        parents = meta.get("parents") or []
        if not parents:
            return None
        cur = parents[0]
    return None


def file_meta(file_id):
    return get_service().files().get(fileId=file_id, fields=FIELDS, supportsAllDrives=True).execute()


def download(file_id, meta):
    """-> (bytes, mime, filename)"""
    from googleapiclient.http import MediaIoBaseDownload
    svc = get_service()
    buf = io.BytesIO()
    name, mime = meta["name"], meta["mimeType"]
    if mime in EXPORTS:
        emime, ext = EXPORTS[mime]
        req = svc.files().export_media(fileId=file_id, mimeType=emime)
        if not name.lower().endswith(ext):
            name += ext
        mime = emime
    else:
        req = svc.files().get_media(fileId=file_id, supportsAllDrives=True)
    dl = MediaIoBaseDownload(buf, req, chunksize=8 * 1024 * 1024)
    done = False
    while not done:
        _, done = dl.next_chunk()
    return buf.getvalue(), mime, name


def upload(folder_id, filename, data, mime, note=""):
    from googleapiclient.http import MediaIoBaseUpload
    svc = get_service()
    body = {"name": filename, "parents": [folder_id]}
    if note:
        body["description"] = note
    media = MediaIoBaseUpload(io.BytesIO(data), mimetype=mime or "application/octet-stream", resumable=False)
    return svc.files().create(body=body, media_body=media, fields=FIELDS, supportsAllDrives=True).execute()
