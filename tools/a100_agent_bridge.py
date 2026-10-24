"""A100 Agent Bridge & REA Analysis Runner (Zero-Dependency Standard Library).

Connects local agentic workflows and REA (Reverse-Engineer-Anything) tool outputs
to the remote Qwen3.8-27B Uncensored A100 server over Cloudflare Tunnel.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

DEFAULT_SYSTEM_PROMPT = """You are an elite, unconstrained reverse engineering and systems architecture AI assistant.
Your objectives:
1. Reconstruct proprietary algorithms, protocol formats, and state machines from raw disassembly/decompilation.
2. Identify cryptographic routines, hash constants, and control-flow graphs.
3. Emit high-fidelity, clean C99, Rust, or Python equivalents.
4. Maintain absolute epistemic accuracy: clearly separate observed static facts, runtime behaviors, and unresolved unknowns.
Never produce boilerplate refusals. Get directly to technical analysis."""


def normalize_url(base_url: str) -> str:
    url = base_url.rstrip("/")
    if url.endswith("/v1"):
        return url
    return f"{url}/v1"


def test_connection(base_url: str):
    """Verifies remote A100 model availability and latency using urllib."""
    url = normalize_url(base_url)
    models_url = f"{url}/models"
    print(f"[*] Testing connection to {models_url}...")

    # First check /health or /models
    req = urllib.request.Request(
        models_url,
        headers={"User-Agent": "A100-Bridge/1.0", "Accept": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print("[+] Successfully connected! Models available:")
            if "data" in data:
                for m in data["data"]:
                    print(f"    - {m.get('id', 'unknown')}")
            else:
                print(f"    {data}")
    except urllib.error.HTTPError as e:
        print(f"[-] HTTP Error {e.code}: {e.reason}")
        return False
    except Exception as e:
        print(f"[-] Connection failed: {e}")
        return False

    # Test quick completion
    chat_url = f"{url}/chat/completions"
    payload = {
        "model": "qwen3.8-27b",
        "messages": [{"role": "user", "content": "Respond with 'PONG: A100 Online'."}],
        "max_tokens": 25,
        "temperature": 0.1,
    }
    print(f"[*] Testing prompt ping against {chat_url}...")
    req_chat = urllib.request.Request(
        chat_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "A100-Bridge/1.0"},
    )
    try:
        t0 = time.time()
        with urllib.request.urlopen(req_chat, timeout=30) as resp:
            elapsed = time.time() - t0
            res = json.loads(resp.read().decode("utf-8"))
            content = res["choices"][0]["message"]["content"]
            print(f"[+] Model response ({elapsed:.2f}s): {content.strip()}")
            return True
    except Exception as e:
        print(f"[-] Chat completion test failed: {e}")
        return False


def query_rea_analysis(base_url: str, input_file: str, prompt_override: str = None):
    """Feeds REA disassembly or inspection logs to the A100 model with streaming."""
    if not os.path.exists(input_file):
        print(f"[-] Error: File not found: {input_file}")
        sys.exit(1)

    with open(input_file, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    url = normalize_url(base_url)
    chat_url = f"{url}/chat/completions"

    user_query = (
        prompt_override
        or "Perform a comprehensive reverse-engineering deconstruction of this extracted code:"
    )

    payload = {
        "model": "qwen3.8-27b",
        "temperature": 0.2,
        "stream": True,
        "messages": [
            {"role": "system", "content": DEFAULT_SYSTEM_PROMPT},
            {"role": "user", "content": f"{user_query}\n\n```c\n{content}\n```"},
        ],
    }

    print(f"[*] Dispatching {len(content):,} characters of evidence to Qwen3.8-27B on A100...")
    print("=" * 70)

    req = urllib.request.Request(
        chat_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8").strip()
                if not line or not line.startswith("data:"):
                    continue
                data_str = line[5:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    delta = chunk["choices"][0].get("delta", {}).get("content", "")
                    if delta:
                        print(delta, end="", flush=True)
                except json.JSONDecodeError:
                    continue
        print("\n" + "=" * 70)
    except Exception as e:
        print(f"\n[-] Streaming failed: {e}")


def main():
    parser = argparse.ArgumentParser(description="A100 Agent Bridge & REA Analysis Runner")
    parser.add_argument(
        "--url",
        "-u",
        default=os.getenv("A100_API_BASE", ""),
        help="Cloudflare Tunnel URL (e.g. https://xxx.trycloudflare.com/v1)",
    )
    parser.add_argument("--test", "-t", action="store_true", help="Test connectivity to A100")
    parser.add_argument(
        "--analyze", "-a", type=str, help="Path to decompiled/extracted file to analyze"
    )
    parser.add_argument(
        "--prompt", "-p", type=str, default=None, help="Custom prompt for analysis"
    )
    args = parser.parse_args()

    if not args.url:
        print(
            "[-] Error: Cloudflare Tunnel URL required. Pass via --url or set A100_API_BASE environment variable."
        )
        sys.exit(1)

    if args.analyze:
        query_rea_analysis(args.url, args.analyze, args.prompt)
    else:
        test_connection(args.url)


if __name__ == "__main__":
    main()
