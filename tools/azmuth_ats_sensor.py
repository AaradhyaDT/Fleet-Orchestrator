#!/usr/bin/env python3
"""tools/azmuth_ats_sensor.py
----------------------------
Azmuth Autonomous ATS Sensory Harvester & Career Alpha Radar (U14).

Monitors high-tier frontier AI labs, sovereign tech hubs, and infrastructure companies
across modern Applicant Tracking Systems (Ashby, Greenhouse, Lever).

Features:
1. Ashby API Engine: Direct JSON endpoint querying (/posting-api/job-board/<board_id>).
2. Greenhouse API Engine: Direct JSON endpoint querying (boards-api.greenhouse.io/v1/boards/<board_token>/jobs).
3. Lever API Engine: Direct JSON endpoint querying (api.lever.co/v0/postings/<board_token>).
4. Thalamic Sieve: Filters roles for high-signal engineering domains:
   - Kernel / CUDA / Hardware Acceleration
   - LLM Inference / Systems / TinyML / Edge AI
   - AI Infrastructure / Distributed Training / Orchestration
   - Autonomous Agents / R&D Engineering
5. Salience Scoring & Ingestion: Computes saliency and persists to cache & brief.
6. Notifier Hook: Dispatches desktop toast alerts for Tier-1 matched openings.
"""

from __future__ import annotations

import argparse
import collections
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

# Root directory anchoring
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

STATE_DIR = ROOT / "orchestrator-state"
ATS_CACHE_FILE = STATE_DIR / "ats_sensor_cache.json"

try:
    from tools.azmuth_notifier import notify_opportunity
except ImportError:
    notify_opportunity = None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [AzmuthATS] %(message)s",
)
logger = logging.getLogger("azmuth_ats_sensor")

# Targeted high-signal companies and their ATS providers
TARGET_BOARDS: List[Dict[str, str]] = [
    {"name": "OpenAI", "provider": "ashby", "board": "openai", "tier": "1"},
    {"name": "Anthropic", "provider": "greenhouse", "board": "anthropic", "tier": "1"},
    {"name": "Palantir", "provider": "lever", "board": "palantir", "tier": "1"},
    {"name": "Cohere", "provider": "lever", "board": "cohere", "tier": "1"},
    {"name": "Mistral", "provider": "lever", "board": "mistral", "tier": "1"},
    {"name": "Scale AI", "provider": "greenhouse", "board": "scaleai", "tier": "1"},
]

KEYWORD_PATTERNS = [
    # Low-level systems & hardware
    "kernel", "cuda", "gpu", "compiler", "acceleration", "tinyml", "edge ai",
    # Inference & Serving
    "inference", "vllm", "quantization", "fp8", "fp4", "triton",
    # Infrastructure & Systems
    "infrastructure", "systems", "platform", "distributed", "compute", "firmware",
    # Research & Autonomy
    "research engineer", "agent", "orchestration", "fellow", "resident"
]


def _fetch_json(url: str, timeout: int = 8) -> Optional[Any]:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AzmuthSensory/2.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.debug("Failed to fetch %s: %s", url, e)
    return None


def fetch_ashby_jobs(board_name: str) -> List[Dict[str, Any]]:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{board_name}"
    data = _fetch_json(url)
    jobs = []
    if data and isinstance(data, dict):
        for raw in data.get("jobs", []):
            jobs.append({
                "id": f"ashby:{board_name}:{raw.get('id', '')}",
                "title": raw.get("title", ""),
                "company": board_name.capitalize(),
                "location": raw.get("location", ""),
                "department": raw.get("department", ""),
                "url": raw.get("jobUrl", ""),
                "provider": "ashby",
            })
    return jobs


def fetch_greenhouse_jobs(board_name: str) -> List[Dict[str, Any]]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{board_name}/jobs"
    data = _fetch_json(url)
    jobs = []
    if data and isinstance(data, dict):
        for raw in data.get("jobs", []):
            jobs.append({
                "id": f"greenhouse:{board_name}:{raw.get('id', '')}",
                "title": raw.get("title", ""),
                "company": board_name.capitalize(),
                "location": raw.get("location", {}).get("name", "") if isinstance(raw.get("location"), dict) else "",
                "department": raw.get("departments", [{}])[0].get("name", "") if raw.get("departments") else "",
                "url": raw.get("absolute_url", ""),
                "provider": "greenhouse",
            })
    return jobs


def fetch_lever_jobs(board_name: str) -> List[Dict[str, Any]]:
    url = f"https://api.lever.co/v0/postings/{board_name}"
    data = _fetch_json(url)
    jobs = []
    if data and isinstance(data, list):
        for raw in data:
            jobs.append({
                "id": f"lever:{board_name}:{raw.get('id', '')}",
                "title": raw.get("text", ""),
                "company": board_name.capitalize(),
                "location": raw.get("categories", {}).get("location", "") if isinstance(raw.get("categories"), dict) else "",
                "department": raw.get("categories", {}).get("department", "") if isinstance(raw.get("categories"), dict) else "",
                "url": raw.get("hostedUrl", ""),
                "provider": "lever",
            })
    return jobs


def score_role_salience(job: Dict[str, Any]) -> float:
    text = f"{job.get('title', '')} {job.get('department', '')}".lower()
    score = 0.0
    for kw in KEYWORD_PATTERNS:
        if kw in text:
            score += 1.0
    return score


def harvest_ats_feed() -> List[Dict[str, Any]]:
    logger.info("Executing ATS sensory sweep across %d target boards...", len(TARGET_BOARDS))
    all_matched = []

    for target in TARGET_BOARDS:
        provider = target["provider"]
        board = target["board"]
        name = target["name"]
        raw_jobs = []

        try:
            if provider == "ashby":
                raw_jobs = fetch_ashby_jobs(board)
            elif provider == "greenhouse":
                raw_jobs = fetch_greenhouse_jobs(board)
            elif provider == "lever":
                raw_jobs = fetch_lever_jobs(board)
        except Exception as e:
            logger.warning("Error harvesting %s (%s): %s", name, provider, e)
            continue

        matched_count = 0
        for job in raw_jobs:
            job["company"] = name
            salience = score_role_salience(job)
            if salience >= 1.0:
                job["salience"] = salience
                job["harvested_at"] = datetime.now(timezone.utc).isoformat()
                all_matched.append(job)
                matched_count += 1

        logger.info("Board %s: Harvested %d total jobs -> %d high-signal matches.", name, len(raw_jobs), matched_count)

    # Sort descending by salience
    all_matched.sort(key=lambda j: j["salience"], reverse=True)

    # Persist to cache
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_matched": len(all_matched),
        "openings": all_matched[:100],  # Top 100
    }
    ATS_CACHE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("Saved %d opportunities to %s", len(all_matched), ATS_CACHE_FILE)

    # Notify top new openings (salience >= 2.0)
    if notify_opportunity:
        notified_count = 0
        for top_job in all_matched[:5]:
            if top_job["salience"] >= 2.0:
                did_notify = notify_opportunity(
                    title=f"🎯 Azmuth ATS: {top_job['company']}",
                    message=f"{top_job['title']} ({top_job['location']})",
                    item_id=top_job["id"],
                    url=top_job.get("url"),
                )
                if did_notify:
                    notified_count += 1
        if notified_count > 0:
            logger.info("Dispatched %d Windows toast notifications for new roles.", notified_count)

    return all_matched


if __name__ == "__main__":
    results = harvest_ats_feed()
    print(f"\nCompleted ATS Harvest. Found {len(results)} high-signal engineering roles.")
    for j in results[:5]:
        print(f" - [{j['company']}] {j['title']} (Salience: {j['salience']}) -> {j['url']}")
