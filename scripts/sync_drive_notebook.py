#!/usr/bin/env python3
"""Upload a local Jupyter notebook (and optional .py mirror) to Google Drive.

Handles create-or-update semantics: if a file with the same name already
exists in the target folder, it is updated in-place (preserving the file ID
and Colab share links). Otherwise, a new file is created.

Usage:
    python sync_drive_notebook.py <NOTEBOOK_PATH> --folder <DRIVE_FOLDER_ID>
    python sync_drive_notebook.py research/EXP-REA-001.ipynb --folder 1cTIWkYMiFwulnWK_zIjvPZ5GZMpsSCN2
    python sync_drive_notebook.py research/EXP-REA-001.ipynb --folder 1cTIWkYMiFwulnWK_zIjvPZ5GZMpsSCN2 --py

Dependencies:
    - scripts/sync_drive.py (for OAuth credentials and find_drive_file_by_name)
    - ~/.gdrive-credentials.json
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
import sync_drive


def upload_or_update(
    local_path: Path,
    folder_id: str,
    access_token: str,
    mime_type: str = "application/json",
) -> str:
    """Upload a file to Google Drive, creating or updating as needed."""
    file_name = local_path.name
    content = local_path.read_bytes()

    existing_id = sync_drive.find_drive_file_by_name(access_token, folder_id, file_name)

    if existing_id:
        url = f"https://www.googleapis.com/upload/drive/v3/files/{existing_id}?uploadType=media"
        req = urllib.request.Request(
            url,
            data=content,
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": mime_type},
            method="PATCH",
        )
        with urllib.request.urlopen(req) as resp:
            fid = json.loads(resp.read().decode())["id"]
        print(f"  [~] Updated {file_name} (ID: {fid})")
        return fid
    else:
        metadata = {"name": file_name, "parents": [folder_id], "mimeType": mime_type}
        boundary = "===============NOTEBOOK_BOUNDARY=="
        body = (
            f"--{boundary}\r\n"
            f"Content-Type: application/json; charset=UTF-8\r\n\r\n"
            f"{json.dumps(metadata)}\r\n"
            f"--{boundary}\r\n"
            f"Content-Type: {mime_type}\r\n\r\n"
        ).encode("utf-8") + content + f"\r\n--{boundary}--\r\n".encode("utf-8")

        req = urllib.request.Request(
            "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart",
            data=body,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": f"multipart/related; boundary={boundary}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            fid = json.loads(resp.read().decode())["id"]
        print(f"  [+] Created {file_name} (ID: {fid})")
        return fid


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload notebook and optional .py mirror to Google Drive")
    parser.add_argument("notebook", type=Path, help="Path to local .ipynb file")
    parser.add_argument("--folder", required=True, help="Google Drive target folder ID")
    parser.add_argument("--py", action="store_true", help="Also upload the .py mirror (same stem, .py extension)")
    args = parser.parse_args()

    if not args.notebook.exists():
        print(f"[!] Notebook not found: {args.notebook}")
        sys.exit(1)

    client_id, client_secret, refresh_token = sync_drive.get_oauth_credentials()
    access_token = sync_drive.obtain_access_token(client_id, client_secret, refresh_token)

    print(f"[*] Uploading {args.notebook.name} to folder {args.folder}")
    upload_or_update(args.notebook, args.folder, access_token, mime_type="application/json")

    if args.py:
        py_path = args.notebook.with_suffix(".py")
        if py_path.exists():
            print(f"[*] Uploading {py_path.name}")
            upload_or_update(py_path, args.folder, access_token, mime_type="text/plain")
        else:
            print(f"[!] .py mirror not found at {py_path}, skipping.")

    print("[SUCCESS] Drive sync complete.")


if __name__ == "__main__":
    main()
