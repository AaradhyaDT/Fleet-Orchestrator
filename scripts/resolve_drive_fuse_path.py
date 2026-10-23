#!/usr/bin/env python3
"""Resolve the full Google Drive FUSE mount path for a folder ID.

Walks the parent chain via the Drive Files API to reconstruct the
complete `/content/drive/MyDrive/...` path that Colab FUSE exposes.

Usage:
    python resolve_drive_fuse_path.py <FOLDER_ID>
    python resolve_drive_fuse_path.py 1cTIWkYMiFwulnWK_zIjvPZ5GZMpsSCN2

Dependencies:
    - scripts/sync_drive.py (for OAuth credentials)
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


def resolve_fuse_path(folder_id: str, access_token: str) -> str:
    """Walk parent chain from folder_id to root, return FUSE mount path."""
    chain: list[str] = []
    fid = folder_id
    for _ in range(15):  # safety cap
        url = f"https://www.googleapis.com/drive/v3/files/{fid}?fields=name,parents"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {access_token}"})
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
        name = data.get("name", "")
        parents = data.get("parents", [])
        chain.append(name)
        if not parents:
            break
        fid = parents[0]

    chain.reverse()
    # chain[0] is typically "My Drive" (root); FUSE maps it to /content/drive/MyDrive
    segments = chain[1:]  # skip root "My Drive"
    return "/content/drive/MyDrive/" + "/".join(segments)


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve Google Drive folder ID to Colab FUSE mount path")
    parser.add_argument("folder_id", help="Google Drive folder ID to resolve")
    parser.add_argument("--file", "-f", default=None, help="Optional filename to append to the resolved path")
    args = parser.parse_args()

    client_id, client_secret, refresh_token = sync_drive.get_oauth_credentials()
    access_token = sync_drive.obtain_access_token(client_id, client_secret, refresh_token)

    fuse_path = resolve_fuse_path(args.folder_id, access_token)
    if args.file:
        fuse_path = fuse_path.rstrip("/") + "/" + args.file

    print(fuse_path)


if __name__ == "__main__":
    main()
