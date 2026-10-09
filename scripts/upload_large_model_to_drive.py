"""Large File Resumable Upload Engine for Google Drive.

Uploads binary ML models (GGUF, safetensors, ONNX) to Google Drive folders
using chunked resumable upload (uploadType=resumable).
Leverages local OAuth credentials from ~/.gdrive-credentials.json.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# Add scripts directory for credential reuse
SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
import sync_drive

DRIVE_RESUMABLE_ENDPOINT = "https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable"
CHUNK_SIZE = 16 * 1024 * 1024  # 16 MB chunks


def upload_resumable(
    file_path: Path,
    folder_id: str,
    access_token: str,
    mime_type: str = "application/octet-stream"
) -> str:
    """Uploads large binary file in chunks via Google Drive Resumable Upload API."""
    file_size = file_path.stat().st_size
    file_name = file_path.name
    print(f"[*] Starting resumable upload for: {file_name}")
    print(f"[*] Size: {file_size / (1024*1024):.2f} MB ({file_size} bytes)")
    print(f"[*] Target Folder: {folder_id}")

    # 1. Initiate Resumable Session
    metadata = {
        "name": file_name,
        "parents": [folder_id],
        "mimeType": mime_type,
    }
    meta_bytes = json.dumps(metadata).encode("utf-8")

    init_req = urllib.request.Request(DRIVE_RESUMABLE_ENDPOINT, data=meta_bytes, method="POST")
    init_req.add_header("Authorization", f"Bearer {access_token}")
    init_req.add_header("Content-Type", "application/json; charset=UTF-8")
    init_req.add_header("X-Upload-Content-Type", mime_type)
    init_req.add_header("X-Upload-Content-Length", str(file_size))

    try:
        with urllib.request.urlopen(init_req, timeout=30) as resp:
            location_url = resp.headers.get("Location")
            if not location_url:
                raise RuntimeError("Failed to get resumable upload session Location URL.")
    except urllib.error.HTTPError as e:
        print(f"[ERROR] Session init failed ({e.code}): {e.read().decode('utf-8', errors='replace')}")
        raise

    print(f"[+] Resumable session established. Uploading in {CHUNK_SIZE // (1024*1024)}MB chunks...")

    # 2. Upload file in chunks
    start_time = time.perf_counter()
    with open(file_path, "rb") as f:
        offset = 0
        while offset < file_size:
            chunk = f.read(CHUNK_SIZE)
            chunk_len = len(chunk)
            end = offset + chunk_len - 1

            chunk_req = urllib.request.Request(location_url, data=chunk, method="PUT")
            chunk_req.add_header("Content-Length", str(chunk_len))
            chunk_req.add_header("Content-Range", f"bytes {offset}-{end}/{file_size}")
            chunk_req.add_header("Content-Type", mime_type)

            for attempt in range(5):
                try:
                    with urllib.request.urlopen(chunk_req, timeout=120) as chunk_resp:
                        if chunk_resp.status in (200, 201):
                            # Completed upload
                            res_body = json.loads(chunk_resp.read().decode("utf-8"))
                            file_id = res_body.get("id")
                            total_time = time.perf_counter() - start_time
                            mbps = (file_size / (1024 * 1024)) / total_time
                            print(f"\n[+] Upload Complete in {total_time:.1f}s ({mbps:.2f} MB/s)!")
                            print(f"[+] Drive File ID: {file_id}")
                            print(f"[+] URL: https://drive.google.com/file/d/{file_id}/view")
                            return file_id
                except urllib.error.HTTPError as e:
                    if e.code == 308:
                        # 308 Resume Incomplete (Expected for intermediate chunks)
                        offset += chunk_len
                        pct = (offset / file_size) * 100.0
                        elapsed = time.perf_counter() - start_time
                        print(f"    -> Progress: {offset / (1024*1024):.1f}/{file_size / (1024*1024):.1f} MB ({pct:.1f}%) [{elapsed:.0f}s]", end="\r", flush=True)
                        break
                    elif e.code in (429, 500, 502, 503, 504) and attempt < 4:
                        print(f"\n[RETRY] HTTP {e.code} on chunk. Backing off 3s...")
                        time.sleep(3)
                        continue
                    else:
                        print(f"\n[ERROR] Chunk upload failed ({e.code}): {e.read().decode('utf-8', errors='replace')}")
                        raise
                except Exception as e:
                    if attempt < 4:
                        print(f"\n[RETRY] Network glitch: {e}. Retrying chunk in 3s...")
                        time.sleep(3)
                        continue
                    raise

    raise RuntimeError("Upload loop terminated without 200/201 response.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload large binary models to Google Drive.")
    parser.add_argument(
        "--file",
        default="F:/Aaradhya-Dev-Tamrakar/Fleet-Orchestrator/models/qwen_intent_router_q4_k_m.gguf",
        help="Path to the model file to upload."
    )
    parser.add_argument(
        "--folder-id",
        default="1wGq53okV7ZaFGSw2fWilEfxL4FEIVeIF",
        help="Google Drive target folder ID."
    )
    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.exists():
        print(f"[ERROR] File does not exist: {file_path}")
        sys.exit(1)

    print("[*] Fetching Google OAuth token...")
    cid, csec, rtok = sync_drive.get_oauth_credentials()
    if not (cid and csec and rtok):
        print("[ERROR] Missing Google Drive OAuth credentials.")
        sys.exit(1)

    token = sync_drive.obtain_access_token(cid, csec, rtok)
    upload_resumable(file_path, args.folder_id, token)


if __name__ == "__main__":
    main()
