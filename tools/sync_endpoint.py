#!/usr/bin/env python3
"""Sync remote A100 Colab endpoint to local IDE configs (Option A: Zero Friction).

Fetches the latest active Cloudflare Tunnel URL from:
1. Google Drive (written automatically by Colab Cell 4 to active_a100_endpoint.json)
2. Windows Clipboard (if user recently copied the trycloudflare.com URL)
3. Command-line flag (--url) or interactive prompt

Once acquired, it:
- Verifies endpoint connectivity and measures latency
- Auto-patches ~/.continue/config.yaml for VS Code Continue
- Updates .env.a100 for local terminals, tools, and Cline

Usage:
    python tools/sync_endpoint.py
    python tools/sync_endpoint.py --url https://your-tunnel.trycloudflare.com/v1
    python tools/sync_endpoint.py --watch
"""

from __future__ import annotations

import argparse
import ctypes
import datetime
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
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


def get_clipboard_url() -> str | None:
    """Read Windows clipboard to see if it holds a tunnel URL."""
    try:
        user32 = ctypes.windll.user32
        if user32.OpenClipboard(0):
            try:
                if user32.IsClipboardFormatAvailable(13):  # CF_UNICODETEXT
                    h_data = user32.GetClipboardData(13)
                    if h_data:
                        kernel32 = ctypes.windll.kernel32
                        kernel32.GlobalLock.restype = ctypes.c_wchar_p
                        p_data = kernel32.GlobalLock(h_data)
                        if p_data:
                            text = str(p_data).strip()
                            kernel32.GlobalUnlock(h_data)
                            match = re.search(
                                r"https://[a-zA-Z0-9-]+\.(?:trycloudflare\.com|ngrok-free\.app|loca\.lt)(?:/v1)?",
                                text,
                            )
                            if match:
                                return match.group(0)
            finally:
                user32.CloseClipboard()
    except Exception:
        pass
    return None


def fetch_endpoint_from_drive() -> dict | None:
    """Fetch active endpoint JSON from Google Drive using sync_drive OAuth."""
    if not sync_drive:
        return None

    try:
        client_id, client_secret, refresh_token = sync_drive.get_oauth_credentials()
        access_token = sync_drive.obtain_access_token(client_id, client_secret, refresh_token)
    except Exception as e:
        print(f"[-] Google Drive token lookup: {e}")
        return None

    # Search for the endpoint file
    queries = [
        f"'{DRIVE_FOLDER_ID}' in parents and name = '{ENDPOINT_FILENAME}' and trashed = false",
        f"name = '{ENDPOINT_FILENAME}' and trashed = false",
    ]

    for query in queries:
        url = f"https://www.googleapis.com/drive/v3/files?q={urllib.parse.quote(query)}&fields=files(id,name,modifiedTime)"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {access_token}"})
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                files = json.loads(resp.read().decode())["files"]
            if files:
                # Get the most recently modified file if multiple exist
                files.sort(key=lambda x: x.get("modifiedTime", ""), reverse=True)
                file_id = files[0]["id"]
                dl_url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
                dl_req = urllib.request.Request(dl_url, headers={"Authorization": f"Bearer {access_token}"})
                with urllib.request.urlopen(dl_req, timeout=8) as dl_resp:
                    content = dl_resp.read().decode("utf-8")
                return json.loads(content)
        except Exception:
            continue

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
        print(f"[!] Warning: Endpoint ping returned: {e}")
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
            print(f"[=] Continue config already set to: {norm_url}")
            return True
        new_text = re.sub(pattern, rf"\g<1>{norm_url}", text)
        CONTINUE_CONFIG_PATH.write_text(new_text, encoding="utf-8")
        print(f"[+] Patched ~/.continue/config.yaml")
        print(f"    Old: {old_url}")
        print(f"    New: {norm_url}")
        return True
    else:
        print("[-] Could not find 'A100 Qwen3.8-27B Uncensored' block in config.yaml.")
        return False


def save_local_env(api_url: str):
    """Save active endpoint to .env.a100 for terminal, REA bridge, and tools."""
    norm_url = api_url.rstrip("/")
    if not norm_url.endswith("/v1"):
        norm_url = f"{norm_url}/v1"

    env_path = REPO_ROOT / ".env.a100"
    content = (
        f"# Auto-generated by tools/sync_endpoint.py\n"
        f"A100_API_BASE={norm_url}\n"
        f"OPENAI_API_BASE={norm_url}\n"
        f"OPENAI_API_KEY=none\n"
        f"CLINE_BASE_URL={norm_url}\n"
    )
    env_path.write_text(content, encoding="utf-8")
    print(f"[+] Saved local environment to {env_path.name}")


def run_sync(manual_url: str | None = None) -> bool:
    print("=" * 60)
    print("  A100 Cloudflare Tunnel Auto-Sync (Option A)")
    print("=" * 60)

    target_url = None

    if manual_url:
        target_url = manual_url
        print(f"[*] Using specified URL: {target_url}")
    else:
        print("[*] Fetching active endpoint from Google Drive...")
        payload = fetch_endpoint_from_drive()
        if payload and "url" in payload:
            target_url = payload["url"]
            ts = payload.get("timestamp")
            if ts:
                dt = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
                print(f"[+] Discovered active URL from Drive: {target_url} (written at {dt})")
            else:
                print(f"[+] Discovered active URL from Drive: {target_url}")
        else:
            print("[-] No active URL found in Google Drive yet.")
            clip_url = get_clipboard_url()
            if clip_url:
                print(f"[+] Found tunnel URL on Windows Clipboard: {clip_url}")
                target_url = clip_url

    if not target_url:
        print("\n[?] Enter Cloudflare Tunnel URL (or Ctrl+C to exit):")
        try:
            target_url = input("> ").strip()
        except KeyboardInterrupt:
            print("\n[-] Cancelled.")
            return False

    if not target_url:
        print("[-] No URL provided. Aborting.")
        return False

    # Patch config.yaml
    update_continue_config(target_url)

    # Save to .env.a100
    save_local_env(target_url)

    # Verify connectivity
    verify_endpoint(target_url)

    print("=" * 60)
    print(f"[READY] VS Code Continue & Cline endpoint: {target_url}")
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
        return

    run_sync(args.url)


if __name__ == "__main__":
    main()
