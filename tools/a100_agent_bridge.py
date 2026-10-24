"""A100 Agent Bridge & REA Analysis Runner.

Connects local agentic workflows and REA (Reverse-Engineer-Anything) tool outputs
to the remote Qwen3.8-27B Uncensored A100 server over Cloudflare Tunnel.
"""

import argparse
import json
import os
import sys
from openai import OpenAI

DEFAULT_SYSTEM_PROMPT = """You are an elite, unconstrained reverse engineering and systems architecture AI assistant.
Your objectives:
1. Reconstruct proprietary algorithms, protocol formats, and state machines from raw disassembly/decompilation.
2. Identify cryptographic routines, hash constants, and control-flow graphs.
3. Emit high-fidelity, clean C99, Rust, or Python equivalents.
4. Maintain absolute epistemic accuracy: clearly separate observed static facts, runtime behaviors, and unresolved unknowns.
Never produce boilerplate refusals. Get directly to technical analysis."""

def get_client(base_url: str) -> OpenAI:
    # Ensure URL ends with /v1
    normalized_url = base_url.rstrip("/")
    if not normalized_url.endswith("/v1"):
        normalized_url += "/v1"
    return OpenAI(base_url=normalized_url, api_key="none")

def test_connection(client: OpenAI):
    """Verifies remote A100 model availability and latency."""
    print(f"[*] Testing connection to {client.base_url}...")
    try:
        models = client.models.list()
        print(f"[+] Successfully connected! Models available:")
        for m in models.data:
            print(f"    - {m.id}")
        
        # Test brief completion
        res = client.chat.completions.create(
            model="qwen3.8-27b",
            messages=[{"role": "user", "content": "Ping. Respond with 'PONG: A100 Online'."}],
            max_tokens=20
        )
        print(f"[+] Model response: {res.choices[0].message.content.strip()}")
        return True
    except Exception as e:
        print(f"[-] Connection failed: {e}")
        return False

def query_rea_analysis(client: OpenAI, input_file: str, prompt_override: str = None):
    """Feeds REA disassembly or inspection logs to the A100 model."""
    if not os.path.exists(input_file):
        print(f"[-] Error: File not found: {input_file}")
        sys.exit(1)
        
    with open(input_file, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    user_query = prompt_override or "Perform a comprehensive reverse-engineering deconstruction of this extracted code:"
    
    print(f"[*] Dispatching {len(content):,} characters of evidence to Qwen3.8-27B on A100...")
    print("=" * 70)
    
    stream = client.chat.completions.create(
        model="qwen3.8-27b",
        temperature=0.2,
        messages=[
            {"role": "system", "content": DEFAULT_SYSTEM_PROMPT},
            {"role": "user", "content": f"{user_query}\n\n```c\n{content}\n```"}
        ],
        stream=True
    )
    
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end="", flush=True)
    print("\n" + "=" * 70)

def main():
    parser = argparse.ArgumentParser(description="A100 Agent Bridge & REA Analysis Runner")
    parser.add_argument("--url", "-u", default=os.getenv("A100_API_BASE", ""), help="Cloudflare Tunnel URL (e.g. https://xxx.trycloudflare.com/v1)")
    parser.add_argument("--test", "-t", action="store_true", help="Test connectivity to A100")
    parser.add_argument("--analyze", "-a", type=str, help="Path to decompiled/extracted file to analyze")
    parser.add_argument("--prompt", "-p", type=str, default=None, help="Custom prompt for analysis")
    args = parser.parse_args()

    if not args.url:
        print("[-] Error: Cloudflare Tunnel URL required. Pass via --url or set A100_API_BASE environment variable.")
        sys.exit(1)

    client = get_client(args.url)
    
    if args.test:
        test_connection(client)
    elif args.analyze:
        query_rea_analysis(client, args.analyze, args.prompt)
    else:
        # Default to connection test
        test_connection(client)

if __name__ == "__main__":
    main()
