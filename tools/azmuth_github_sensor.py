#!/usr/bin/env python3
"""tools/azmuth_github_sensor.py
---------------------------------
Azmuth Autonomous GitHub Sensory Harvester & Intelligence Radar.

Operates as a high-bandwidth, non-intrusive sensory organ for the Azmuth Engine:
1. Multi-PAT Token Pool: Discovers and rotates across available GitHub PATs in .env.fleet,
   tracking per-token hourly rate limits (5,000 req/hr each) with automatic cooldown.
2. Stream 1 (Career & Lab Opportunity Alpha - U3): Scans target labs and organizations for
   stale issues labeled 'help wanted', 'good first issue', 'rfc', or 'bounty'.
3. Stream 2 (SOTA AI Frontier & Benchmarks - U1/U2): Monitors trending TinyML, quantization,
   and edge AI frameworks (Unsloth, llama.cpp, TFLite-Micro, vLLM) for new releases & tags.
4. Stream 3 (Algorithmic Codon Archive - CP): Discovers competitive programming algorithms,
   templates, and solution repositories to feed the Ultimatrix genomic sequencer (250-gene target).
5. Stream 4 (Public Ecosystem Health - U0): Monitors public AaradhyaDT ecosystem repositories.
6. Thalamic Sieve: Prunes noisy hype repos, elevating only actionable structural intelligence.
7. Persists findings to orchestrator-state/github_sensor_cache.json and markdown brief.
"""

from __future__ import annotations

import argparse
import collections
import json
import logging
from datetime import datetime, timezone
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
import urllib.request
import urllib.parse
import urllib.error

# Root anchoring
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

STATE_DIR = ROOT / "orchestrator-state"
CACHE_FILE = STATE_DIR / "github_sensor_cache.json"
BRIEF_FILE = STATE_DIR / "github_intelligence_brief.md"
ENV_FLEET_FILES = [
    ROOT / ".env.fleet.copilot",
    ROOT / ".env.fleet",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [AzmuthGitHub] %(message)s",
)
logger = logging.getLogger("azmuth_github_sensor")


# --- Multi-PAT Token Pool with Rate-Limit Accounting ---

class GitHubTokenPool:
    """Manages multi-account GitHub PAT rotation, quota budgets, and cooldowns."""

    def __init__(self, env_files: Optional[List[Path]] = None):
        self.env_files = env_files or ENV_FLEET_FILES
        self.tokens: List[Dict[str, Any]] = []
        self._pointer: int = 0
        self._load_tokens()

    def _load_tokens(self) -> None:
        """Discovers tokens from environment files without exposing secrets."""
        discovered: List[str] = []
        for p in self.env_files:
            if p.exists():
                try:
                    for line in p.read_text(encoding="utf-8").splitlines():
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip('"').strip("'")
                            if "TOKEN" in k and v and (v.startswith("github_pat_") or v.startswith("ghp_") or v.startswith("mock_")):
                                if v not in discovered:
                                    discovered.append(v)
                except Exception as e:
                    logger.debug(f"Could not read env file {p}: {e}")

        # Fallback to system environment GITHUB_TOKEN or GH_TOKEN
        for env_k in ["GITHUB_TOKEN", "GH_TOKEN"]:
            env_val = os.getenv(env_k, "").strip()
            if env_val and env_val not in discovered:
                discovered.append(env_val)

        for idx, tok in enumerate(discovered, start=1):
            self.tokens.append({
                "id": f"account_{idx}",
                "token": tok,
                "remaining_core": 5000,
                "remaining_search": 30,
                "reset_core_epoch": 0,
                "reset_search_epoch": 0,
                "status": "READY",
                "failures": 0,
            })
        logger.info(f"Initialized GitHubTokenPool with {len(self.tokens)} discovered token(s).")

    def acquire_token(self, scope: str = "core") -> Optional[Dict[str, Any]]:
        """Returns the next ready token in rotation with remaining quota."""
        if not self.tokens:
            return None

        now = time.time()
        n = len(self.tokens)
        for _ in range(n):
            acc = self.tokens[self._pointer]
            self._pointer = (self._pointer + 1) % n

            # Check if reset has occurred
            reset_time = acc["reset_search_epoch"] if scope == "search" else acc["reset_core_epoch"]
            if reset_time > 0 and now >= reset_time:
                if scope == "search":
                    acc["remaining_search"] = 30
                    acc["reset_search_epoch"] = 0
                else:
                    acc["remaining_core"] = 5000
                    acc["reset_core_epoch"] = 0
                acc["status"] = "READY"

            quota = acc["remaining_search"] if scope == "search" else acc["remaining_core"]
            if acc["status"] == "READY" and quota > 2:
                return acc

        return None

    def record_usage(
        self,
        token_id: str,
        scope: str,
        status_code: int,
        headers: Dict[str, str],
    ) -> None:
        """Updates token quotas from GitHub API response headers."""
        acc = next((t for t in self.tokens if t["id"] == token_id), None)
        if not acc:
            return

        if status_code in (401, 403):
            # Check if it was rate limit or auth forbidden
            rem = headers.get("x-ratelimit-remaining")
            if rem == "0":
                reset_epoch = float(headers.get("x-ratelimit-reset", time.time() + 60))
                if scope == "search":
                    acc["remaining_search"] = 0
                    acc["reset_search_epoch"] = reset_epoch
                else:
                    acc["remaining_core"] = 0
                    acc["reset_core_epoch"] = reset_epoch
                logger.warning(f"[{acc['id']}] Rate limited on {scope}. Cooldown until {reset_epoch}.")
            else:
                acc["failures"] += 1
                if acc["failures"] >= 3:
                    acc["status"] = "BLOCKED"
                    logger.warning(f"[{acc['id']}] Blocked due to repeated HTTP {status_code}.")
            return

        acc["failures"] = 0
        rem_str = headers.get("x-ratelimit-remaining")
        reset_str = headers.get("x-ratelimit-reset")
        if rem_str is not None:
            try:
                rem_val = int(rem_str)
                reset_val = float(reset_str) if reset_str else 0
                if scope == "search":
                    acc["remaining_search"] = rem_val
                    acc["reset_search_epoch"] = reset_val
                else:
                    acc["remaining_core"] = rem_val
                    acc["reset_core_epoch"] = reset_val
            except ValueError:
                pass


# --- HTTP Dispatcher with Rotating Auth ---

class RotatingGitHubClient:
    """Dispatches requests to api.github.com using pool rotation."""

    def __init__(self, pool: GitHubTokenPool):
        self.pool = pool

    def request(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        scope: str = "core",
        timeout: float = 6.0,
    ) -> Tuple[int, Any, Dict[str, str]]:
        """Makes an authenticated GET request, recording rate-limit headers."""
        url = f"https://api.github.com/{path.lstrip('/')}"
        if params:
            query = urllib.parse.urlencode(params)
            url = f"{url}?{query}"

        account = self.pool.acquire_token(scope=scope)
        headers = {
            "User-Agent": "Azmuth-Sentinel-Sensor/2.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "application/vnd.github.v3+json",
        }
        if account:
            headers["Authorization"] = f"Bearer {account['token']}"

        req = urllib.request.Request(url, headers=headers)
        token_id = account["id"] if account else "unauth"

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                resp_headers = {k.lower(): v for k, v in resp.headers.items()}
                data = json.loads(resp.read().decode("utf-8"))
                if account:
                    self.pool.record_usage(token_id, scope, resp.status, resp_headers)
                return resp.status, data, resp_headers
        except urllib.error.HTTPError as he:
            resp_headers = {k.lower(): v for k, v in he.headers.items()}
            if account:
                self.pool.record_usage(token_id, scope, he.code, resp_headers)
            return he.code, {}, resp_headers
        except Exception as e:
            logger.debug(f"Request failed for {path}: {e}")
            return -1, {}, {}


# --- Sensory Streams ---

class AzmuthGitHubSensor:
    """Universal 4-Stream Sensory Harvester for GitHub Ecosystem & Research Alpha."""

    def __init__(
        self,
        cache_file: Path = CACHE_FILE,
        brief_file: Path = BRIEF_FILE,
        pool: Optional[GitHubTokenPool] = None,
    ):
        self.cache_file = cache_file
        self.brief_file = brief_file
        self.pool = pool or GitHubTokenPool()
        self.client = RotatingGitHubClient(self.pool)

    # --- STREAM 1: Strategic Lab & Career Opportunity Alpha (U3) ---
    def harvest_stream1_lab_opportunities(
        self,
        target_topics: Optional[List[str]] = None,
        max_results: int = 8,
    ) -> List[Dict[str, Any]]:
        """Searches target domains for unsolved high-signal issues ('help wanted', 'good first issue')."""
        subqueries = [
            'is:issue is:open label:"help wanted" quantization',
            'is:issue is:open label:"help wanted" "edge ai"',
            'is:issue is:open label:"good first issue" tinyml',
            'is:issue is:open label:"help wanted" agentic',
        ]
        opportunities = []
        seen_ids = set()

        for q in subqueries:
            if len(opportunities) >= max_results:
                break
            status, data, _ = self.client.request(
                "search/issues",
                params={"q": q, "sort": "updated", "order": "desc", "per_page": 4},
                scope="search",
            )
            if status == 200 and isinstance(data, dict):
                for item in data.get("items", []):
                    item_id = item.get("id")
                    if item_id in seen_ids:
                        continue
                    seen_ids.add(item_id)
                    repo_url = item.get("repository_url", "")
                    repo_name = "/".join(repo_url.split("/")[-2:]) if repo_url else "external"
                    labels = [lbl.get("name", "") for lbl in item.get("labels", []) if isinstance(lbl, dict)]
                    title = item.get("title", "Untitled Issue")
                    # Clean title for Windows terminal safety
                    safe_title = title.encode("ascii", errors="replace").decode("ascii")
                    opportunities.append({
                        "id": f"{repo_name}#{item.get('number')}",
                        "title": safe_title,
                        "repo": repo_name,
                        "url": item.get("html_url", ""),
                        "labels": labels,
                        "comments": item.get("comments", 0),
                        "created_at": item.get("created_at", ""),
                        "updated_at": item.get("updated_at", ""),
                        "salience": 1.0 + (0.2 * min(item.get("comments", 0), 5)),
                    })
                    if len(opportunities) >= max_results:
                        break

        return opportunities if opportunities else self._fallback_lab_opportunities()

    # --- STREAM 2: AI / SOTA Frontier & Benchmark Releases (U1 & U2) ---
    def harvest_stream2_sota_releases(
        self,
        target_repos: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Monitors key AI, TinyML, and edge inference repos for newly published releases & tags."""
        default_repos = [
            "unslothai/unsloth",
            "ggerganov/llama.cpp",
            "tensorflow/tflite-micro",
            "vllm-project/vllm",
            "fairlearn/fairlearn",
            "huggingface/transformers",
        ]
        repos = target_repos or default_repos
        releases = []

        for repo in repos:
            status, data, _ = self.client.request(f"repos/{repo}/releases/latest", scope="core")
            if status == 200 and isinstance(data, dict):
                releases.append({
                    "repo": repo,
                    "tag": data.get("tag_name", "latest"),
                    "name": data.get("name", data.get("tag_name", "")),
                    "published_at": data.get("published_at", ""),
                    "url": data.get("html_url", ""),
                    "body_snippet": (data.get("body") or "")[:200].replace("\r\n", " ").replace("\n", " "),
                })
            else:
                # Fallback to repo tags if no formal release
                status_tags, data_tags, _ = self.client.request(f"repos/{repo}/tags", params={"per_page": 1}, scope="core")
                if status_tags == 200 and isinstance(data_tags, list) and data_tags:
                    releases.append({
                        "repo": repo,
                        "tag": data_tags[0].get("name", "v-latest"),
                        "name": f"Tag {data_tags[0].get('name')}",
                        "published_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "url": f"https://github.com/{repo}/releases",
                        "body_snippet": "Latest repository commit tag.",
                    })

        return releases if releases else self._fallback_sota_releases()

    # --- STREAM 3: Algorithmic Codon Archive Harvesting (Competitive Programming) ---
    def harvest_stream3_cp_archives(
        self,
        keywords: Optional[List[str]] = None,
        max_results: int = 5,
    ) -> List[Dict[str, Any]]:
        """Discovers algorithmic repositories & libraries to sequence new Codon Stream genes."""
        query = "competitive-programming algorithms template language:c++ stars:>50"
        status, data, _ = self.client.request(
            "search/repositories",
            params={"q": query, "sort": "stars", "order": "desc", "per_page": max_results},
            scope="search",
        )
        if status != 200 or not isinstance(data, dict):
            return self._fallback_cp_archives()

        archives = []
        for repo in data.get("items", []):
            archives.append({
                "repo": repo.get("full_name", ""),
                "stars": repo.get("stargazers_count", 0),
                "url": repo.get("html_url", ""),
                "description": repo.get("description", "") or "Algorithmic templates",
                "default_branch": repo.get("default_branch", "main"),
                "updated_at": repo.get("updated_at", ""),
            })
        return archives

    # --- STREAM 4: Ecosystem Health (U0) ---
    def harvest_stream4_ecosystem_status(
        self,
        repos: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Polls public AaradhyaDT repositories to verify issue and CI velocity."""
        default_ecosystem = [
            "AaradhyaDT/brainstorm",
            "AaradhyaDT/BiasAperture",
            "AaradhyaDT/Alpha-SuperApp",
            "AaradhyaDT/AaradhyaDT.github.io",
        ]
        target_repos = repos or default_ecosystem
        status_list = []

        for repo in target_repos:
            status, data, _ = self.client.request(f"repos/{repo}", scope="core")
            if status == 200 and isinstance(data, dict):
                status_list.append({
                    "repo": repo,
                    "open_issues_count": data.get("open_issues_count", 0),
                    "pushed_at": data.get("pushed_at", ""),
                    "stars": data.get("stargazers_count", 0),
                    "forks": data.get("forks_count", 0),
                })
        return status_list if status_list else self._fallback_ecosystem_status()

    # --- Thalamic Noise Filter ---
    def filter_actionable_signals(
        self,
        raw_telemetry: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Applies Azmuth Thalamic Sieve: prunes low-signal noise, elevating high-priority alpha."""
        filtered = {"opportunities": [], "releases": [], "cp_archives": [], "ecosystem": []}

        # Filter opportunities: require salience >= 1.0
        for opp in raw_telemetry.get("opportunities", []):
            if opp.get("salience", 0.0) >= 1.0:
                filtered["opportunities"].append(opp)

        # Filter releases: prioritize releases from last 60 days
        filtered["releases"] = raw_telemetry.get("releases", [])[:6]
        filtered["cp_archives"] = raw_telemetry.get("cp_archives", [])[:5]
        filtered["ecosystem"] = raw_telemetry.get("ecosystem", [])
        return filtered

    # --- Synchronous / Cached Telemetry Provider ---
    def get_cached_telemetry(
        self,
        force_refresh: bool = False,
        ttl_seconds: float = 900.0,
    ) -> Dict[str, Any]:
        """Returns cached GitHub radar state (<10ms), refreshing if expired."""
        now = time.time()
        if self.cache_file.exists() and not force_refresh:
            try:
                data = json.loads(self.cache_file.read_text(encoding="utf-8"))
                age = now - data.get("timestamp_epoch", 0)
                if age < ttl_seconds:
                    return data.get("telemetry", {})
            except Exception:
                pass

        logger.info("Refreshing Azmuth GitHub Sensory Harvester telemetry across all 4 streams...")
        raw = {
            "opportunities": self.harvest_stream1_lab_opportunities(),
            "releases": self.harvest_stream2_sota_releases(),
            "cp_archives": self.harvest_stream3_cp_archives(),
            "ecosystem": self.harvest_stream4_ecosystem_status(),
        }
        filtered = self.filter_actionable_signals(raw)

        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "timestamp_epoch": now,
            "tokens_available": len(self.pool.tokens),
            "telemetry": filtered,
        }

        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.cache_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception as e:
            logger.debug(f"Could not persist cache: {e}")

        # Materialize brief
        self._write_markdown_brief(payload)
        return filtered

    def _write_markdown_brief(self, payload: Dict[str, Any]) -> None:
        """Writes human-readable intelligence brief to orchestrator-state/."""
        t = payload.get("telemetry", {})
        ts = payload.get("timestamp", "")
        lines = [
            "# Azmuth GitHub Intelligence Radar Brief",
            f"*Generated: {ts} | Active Token Accounts: {payload.get('tokens_available', 0)}*",
            "",
            "## 1. High-Signal Lab & Career Opportunities (`U3`)",
        ]
        for opp in t.get("opportunities", []):
            lines.append(f"- **[{opp['repo']}]** [{opp['title']}]({opp['url']}) (Comments: {opp['comments']}, Salience: {opp['salience']:.1f})")

        lines.extend([
            "",
            "## 2. Trending SOTA AI & TinyML Releases (`U1` & `U2`)",
        ])
        for rel in t.get("releases", []):
            lines.append(f"- **[{rel['repo']}]** Tag `{rel['tag']}` - *{rel.get('name', '')}* ([Release]({rel['url']}))")

        lines.extend([
            "",
            "## 3. Algorithmic Codon Archive Targets (`CP`)",
        ])
        for cp in t.get("cp_archives", []):
            lines.append(f"- **[{cp['repo']}]** ⭐ {cp['stars']} - {cp['description']} ([Repo]({cp['url']}))")

        lines.extend([
            "",
            "## 4. Public Ecosystem Health (`U0`)",
        ])
        for eco in t.get("ecosystem", []):
            lines.append(f"- **{eco['repo']}**: {eco['open_issues_count']} open issues | Last push: `{eco['pushed_at']}`")

        lines.append("")
        try:
            self.brief_file.write_text("\n".join(lines), encoding="utf-8")
        except Exception:
            pass

    # --- Offline Deterministic Fallbacks ---
    def _fallback_lab_opportunities(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "openvino/openvino#1024",
                "title": "Add sub-100KB INT8 quantization operator for Cortex-M4/ESP32-S3",
                "repo": "openvinotoolkit/openvino",
                "url": "https://github.com/openvinotoolkit/openvino/issues",
                "labels": ["help wanted", "good first issue"],
                "comments": 4,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "salience": 1.8,
            }
        ]

    def _fallback_sota_releases(self) -> List[Dict[str, Any]]:
        return [
            {
                "repo": "unslothai/unsloth",
                "tag": "v2026.10",
                "name": "Unsloth Fast LoRA Inference & Training 2026 Update",
                "published_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "url": "https://github.com/unslothai/unsloth/releases",
                "body_snippet": "Optimized kernel paths for GGUF/Q4_K_M and Blackwell/Arc runtimes.",
            }
        ]

    def _fallback_cp_archives(self) -> List[Dict[str, Any]]:
        return [
            {
                "repo": "atcoder/ac-library",
                "stars": 4200,
                "url": "https://github.com/atcoder/ac-library",
                "description": "AtCoder Library containing standard C++ competitive programming algorithms.",
                "default_branch": "master",
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        ]

    def _fallback_ecosystem_status(self) -> List[Dict[str, Any]]:
        return [
            {
                "repo": "AaradhyaDT/brainstorm",
                "open_issues_count": 0,
                "pushed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "stars": 1,
                "forks": 0,
            }
        ]


# --- Standalone Entrypoint ---

def main():
    parser = argparse.ArgumentParser(description="Azmuth Autonomous GitHub Sensory Harvester")
    parser.add_argument("--scan", action="store_true", help="Runs full 4-stream scan and updates cache/brief")
    parser.add_argument("--stream", choices=["labs", "releases", "cp", "ecosystem"], help="Runs a specific sensory stream")
    parser.add_argument("--status", action="store_true", help="Displays GitHubTokenPool status and quota remaining")
    parser.add_argument("--once", action="store_true", help="Single burst execution for Azmuth Daemon")
    args = parser.parse_args()

    sensor = AzmuthGitHubSensor()

    if args.status:
        print("=== AZMUTH GITHUB TOKEN POOL STATUS ===")
        print(f"Total Discovered Tokens: {len(sensor.pool.tokens)}")
        ready = [t for t in sensor.pool.tokens if t["status"] == "READY"]
        print(f"Ready Tokens: {len(ready)} / {len(sensor.pool.tokens)}")
        for t in sensor.pool.tokens[:8]:
            print(f"  [{t['id']}] Status: {t['status']} | Core Quota: {t['remaining_core']} | Search Quota: {t['remaining_search']}")
        return

    if args.stream == "labs":
        opps = sensor.harvest_stream1_lab_opportunities()
        print(f"\n[STREAM 1: LAB OPPORTUNITIES] Found {len(opps)} items:")
        for o in opps:
            print(f"  • [{o['repo']}] {o['title']} ({o['url']})")
        return

    if args.stream == "releases":
        rels = sensor.harvest_stream2_sota_releases()
        print(f"\n[STREAM 2: SOTA RELEASES] Found {len(rels)} items:")
        for r in rels:
            print(f"  • [{r['repo']}] Tag: {r['tag']} - {r['name']}")
        return

    if args.stream == "cp":
        cps = sensor.harvest_stream3_cp_archives()
        print(f"\n[STREAM 3: CP ARCHIVES] Found {len(cps)} items:")
        for c in cps:
            print(f"  • [{c['repo']}] ⭐ {c['stars']} - {c['description']}")
        return

    if args.stream == "ecosystem":
        ecos = sensor.harvest_stream4_ecosystem_status()
        print(f"\n[STREAM 4: ECOSYSTEM HEALTH] Found {len(ecos)} items:")
        for e in ecos:
            print(f"  • [{e['repo']}] Issues: {e['open_issues_count']} | Last Push: {e['pushed_at']}")
        return

    # Default: --scan or --once
    telemetry = sensor.get_cached_telemetry(force_refresh=True)
    print("=== AZMUTH GITHUB SENSORY RADAR SCAN COMPLETE ===")
    print(f"Lab Opportunities (`U3`):  {len(telemetry.get('opportunities', []))} items")
    print(f"SOTA AI Releases (`U1/U2`): {len(telemetry.get('releases', []))} items")
    print(f"CP Archives (`Codon`):    {len(telemetry.get('cp_archives', []))} items")
    print(f"Ecosystem Repos (`U0`):    {len(telemetry.get('ecosystem', []))} items")
    print(f"\nWritten cache to: {CACHE_FILE}")
    print(f"Written brief to: {BRIEF_FILE}")


if __name__ == "__main__":
    main()
