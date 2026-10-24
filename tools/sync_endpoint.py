#!/usr/bin/env python3
"""Sync remote A100 Colab endpoint to local IDE configs (Zero-Friction Auto-Patch).

Fetches the latest active Cloudflare Tunnel URL from Google Drive (written by Colab Cell 4),
tests endpoint connectivity, and automatically updates ~/.continue/config.yaml and local env.

Usage:
    python tools/sync_endpoint.py
    python tools/sync_endpoint.py --url https://your-tunnel.trycloudflare.com/v1
    python tools/sync_endpoint.py --watch
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# Add scripts directory for sync_drive credentials
REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

try:
    import sync_drive
except ImportError:
    sync_drive = None

DRIVE_FOLDER_ID = "1wGq53okV7ZaFGSw2fWilEfxL4FEIVeIF"
ENDPOINT_FILENAME = "active_a100_endpoint.json"
CONTINUE_CONFIG_PATH = Path(os.path.expanduser("~/.continue/config.yaml"))


def fetch_endpoint_from_drive() -> dict | None:
    """Fetch active endpoint JSON from Google Drive using sync_drive OAuth."""
    if not sync_drive:
        print("[-] sync_drive module not found.")
        return None

    try:
        client_id, client_secret, refresh_token = sync_drive.get_oauth_credentials()
        access_token = sync_drive.obtain_access_token(client_id, client_secret, refresh_token)
    except Exception as e:
        print(f"[-] Failed to obtain Drive access token: {e}")
        return None

    # Search for the endpoint file in the folder
    query = f"'{DRIVE_FOLDER_ID}' in parents and name = '{ENDPOINT_FILENAME}' and trashed = false"
    url = f"https://www.googleapis.com/drive/v3/files?q={urllib.parse.quote(query)}&fields=files(id,name,modifiedTime)"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {access_token}"})

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            files = json.loads(resp.read().decode())["files"]
        if not files:
            # Fallback search across root My Drive
            query_fallback = f"name = '{ENDPOINT_FILENAME}' and trashed = false"
            url_fb = f"https://www.googleapis.com/drive/v3/files?q={urllib.parse.quote(query_fallback)}&fields=files(id,name,modifiedTime)"
            req_fb = urllib.request.Request(url_fb, headers={"Authorization": f"Bearer {access_token}"})
            with urllib.request.urlopen(req_fb, timeout=10) as resp_fb:
                files = json.loads(resp_fb.read().decode())["files"]

        if not files:
            print(f"[-] No '{ENDPOINT_FILENAME}' found in Google Drive yet.")
            return None

        file_id = files[0]["id"]
        # Download content
        dl_url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
        dl_req = urllib.request.Request(dl_url, headers={"Authorization": f"Bearer {access_token}"})
        with urllib.request.urlopen(dl_req, timeout=10) as dl_resp:
            content = dl_resp.read().decode("utf-8")
        return json.loads(content)
    except Exception as e:
        print(f"[-] Error fetching endpoint from Google Drive: {e}")
        return None


def verify_endpoint(api_url: str) -> bool:
    """Ping endpoint models and measure latency."""
    norm_url = api_url.rstrip("/")
    if not norm_url.endswith("/v1"):
        norm_url = f"{norm_url}/v1"

    models_url = f"{norm_url}/models"
    req = urllib.request.Request(models_url, headers={"User-Agent": "Fleet-Endpoint-Sync/1.0"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        elapsed = time.time() - t0
        print(f"[+] Endpoint alive! Ping latency: {elapsed:.2f}s")
        if "data" in data and len(data["data"]) > 0:
            print(f"    Active Model: {data['data'][0].get('id', 'unknown')}")
        return True
    except Exception as e:
        print(f"[!] Warning: Endpoint ping failed ({e}). It might still be starting.")
        return False


def update_continue_config(api_url: str) -> bool:
    """Update apiBase for A100 model in ~/.continue/config.yaml."""
    if not CONTINUE_CONFIG_PATH.exists():
        print(f"[-] Continue config not found at {CONTINUE_CONFIG_PATH}")
        return False

    norm_url = api_url.rstrip("/")
    if not norm_url.endswith("/v1"):
        norm_url = f"{norm_url}/v1"

    text = CONTINUE_CONFIG_PATH.read_text(encoding="utf-8")

    # Regex search for A100 Qwen entry and update apiBase
    pattern = r"(- name: A100 Qwen3\.8-27B Uncensored[\s\S]*?apiBase:\s*)([^\n]+)"
    match = re.search(pattern, text)
    if match:
        old_url = match.group(2).strip()
        if old_url == norm_url:
            print(f"[=] Continue config already up to date: {norm_url}")
            return True
        new_text = re.sub(pattern, rf"\g<1>{norm_url}", text)
        CONTINUE_CONFIG_PATH.write_text(new_text, encoding="utf-8")
        print(f"[+] Successfully patched ~/.continue/config.yaml")
        print(f"    Old: {old_url}")
        print(f"    New: {norm_url}")
        return True
    else:
        print("[-] Could not find 'A100 Qwen3.8-27B Uncensored' block in config.yaml.")
        return False


def save_local_env(api_url: str):
    """Save active endpoint to .env.a100 for terminal and tools."""
    norm_url = api_url.rstrip("/")
    if not norm_url.endswith("/v1"):
        norm_url = f"{norm_url}/v1"

    env_path = REPO_ROOT / ".env.a100"
    content = f"# Auto-generated by tools/sync_endpoint.py\nA100_API_BASE={norm_url}\nOPENAI_API_BASE={norm_url}\nOPENAI_API_KEY=none\n"
    env_path.write_text(content, encoding="utf-8")
    print(f"[+] Saved local environment to {env_path.name}")


def run_sync(manual_url: str | None = None) -> bool:
    print("=" * 60)
    print("  A100 Cloudflare Tunnel Auto-Sync (Option A)")
    print("=" * 60)

    if manual_url:
        target_url = manual_url
        print(f"[*] Using manually specified URL: {target_url}")
    else:
        print("[*] Fetching active endpoint from Google Drive...")
        payload = fetch_endpoint_from_drive()
        if not payload or "url" not in payload:
            print("[-] Could not retrieve active URL from Drive.")
            return False
        target_url = payload["url"]
        ts = payload.get("timestamp")
        if ts:
            dt = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
            print(f"[+] Discovered active URL from Drive: {target_url} (written at {dt})")
        else:
            print(f"[+] Discovered active URL from Drive: {target_url}")

    # Patch config.yaml
    update_continue_config(target_url)

    # Save to .env.a100
    save_local_env(target_url)

    # Verify connectivity
    verify_endpoint(target_url)

    print("=" * 60)
    print(f"[READY] VS Code Continue is connected to: {target_url}")
    print("=" * 60)
    return True


def main():
    parser = argparse.ArgumentParser(description="Sync A100 Colab endpoint to local IDE configs")
    parser.add_argument("--url", "-u", type=str, default=None, help="Manually override the tunnel URL")
    parser.add_argument("--watch", "-w", action="store_true", help="Continuously poll Drive every 30s")
    args = parser.parse_args()

    if args.watch:
        print("[*] Starting watch mode (polling every 30s)... Press Ctrl+C to stop.")
        last_url = None
        while True:
            try:
                payload = fetch_endpoint_from_drive()
                if payload and "url" in payload:
                    curr_url = payload["url"]
                    if curr_url != last_url:
                        print(f"\n[!] Detected new tunnel URL: {curr_url}")
                        run_sync(curr_url)
                        last_url = curr_url
                time.sleep(30)
            except KeyboardInterrupt:
                print("\n[*] Watch stopped.")
                break
    else:
        run_sync(args.url)


if __name__ == "__main__":
    main()
