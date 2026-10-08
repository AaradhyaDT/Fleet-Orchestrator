#!/usr/bin/env python3
"""
dispatch_iv_ii_tasks.py
Fleet-Orchestrator task dispatcher for IV-II Academic Course Study Pack synthesis.
Enqueues tasks into orchestrator-state/tasks/ following the declarative SKU DAG.
"""

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_TASKS_DIR = REPO_ROOT / "orchestrator-state" / "tasks"
SKU_TEMPLATE = REPO_ROOT / "sku-templates" / "iv_ii_course_study_pack.json"

COURSES = [
    {
        "code": "EX 756",
        "title": "Telecommunications",
        "syllabus": r"D:\Misc Aaradhya\Electronics (NEW 075-079)\[IV-II]\Telecommunication\Telecommunication_BEIE_IV_II_Syllabus.md",
        "source_dir": r"D:\Misc Aaradhya\Electronics (NEW 075-079)\[IV-II]\Telecommunication",
        "target_hub": r"D:\Misc Aaradhya\Electronics (NEW 075-079)\[IV-II]\Telecommunication\StudyHub.md"
    },
    {
        "code": "CE 752",
        "title": "Engineering Professional Practice",
        "syllabus": r"D:\Misc Aaradhya\Electronics (NEW 075-079)\[IV-II]\Engineering Professional Practice\EPP_BEIE_IV_II_Syllabus.md",
        "source_dir": r"D:\Misc Aaradhya\Electronics (NEW 075-079)\[IV-II]\Engineering Professional Practice",
        "target_hub": r"D:\Misc Aaradhya\Electronics (NEW 075-079)\[IV-II]\Engineering Professional Practice\StudyHub.md"
    },
    {
        "code": "EX 758",
        "title": "Energy, Environment and Society",
        "syllabus": r"D:\Misc Aaradhya\Electronics (NEW 075-079)\[IV-II]\Energy, Environment and Society\EES_BEIE_IV_II_Syllabus.md",
        "source_dir": r"D:\Misc Aaradhya\Electronics (NEW 075-079)\[IV-II]\Energy, Environment and Society",
        "target_hub": r"D:\Misc Aaradhya\Electronics (NEW 075-079)\[IV-II]\Energy, Environment and Society\StudyHub.md"
    },
    {
        "code": "CT 751",
        "title": "Information Systems",
        "syllabus": r"D:\Misc Aaradhya\Electronics (NEW 075-079)\[IV-II]\Information System\Information_Systems_BEIE_IV_II_Syllabus.md",
        "source_dir": r"D:\Misc Aaradhya\Electronics (NEW 075-079)\[IV-II]\Information System",
        "target_hub": r"D:\Misc Aaradhya\Electronics (NEW 075-079)\[IV-II]\Information System\StudyHub.md"
    }
]

def main(dry_run: bool = False):
    print("=== Fleet-Orchestrator: IV-II Study Pack Task Dispatcher ===")
    print(f"Tasks Directory: {STATE_TASKS_DIR}")
    print(f"Dry Run: {dry_run}")

    if not SKU_TEMPLATE.exists():
        print(f"ERROR: SKU template missing at {SKU_TEMPLATE}")
        sys.exit(1)

    STATE_TASKS_DIR.mkdir(parents=True, exist_ok=True)

    enqueued = []
    now_iso = datetime.now(timezone.utc).isoformat()

    for c in COURSES:
        task_id = f"task_iv_ii_{c['code'].replace(' ', '_').lower()}_{uuid.uuid4().hex[:6]}"
        task_record = {
            "id": task_id,
            "sku_id": "iv_ii_course_study_pack",
            "course_code": c["code"],
            "course_title": c["title"],
            "syllabus_path": c["syllabus"],
            "source_directory": c["source_dir"],
            "target_hub": c["target_hub"],
            "status": "pending",
            "pipeline_stages": ["research", "draft", "qa", "format"],
            "current_stage": "research",
            "priority": "high",
            "created_at": now_iso
        }

        task_path = STATE_TASKS_DIR / f"{task_id}.json"
        print(f"Enqueuing task: {task_id} for {c['code']} - {c['title']}")

        if not dry_run:
            with open(task_path, "w", encoding="utf-8") as f:
                json.dump(task_record, f, indent=2)
            enqueued.append(task_id)

    print(f"=== Successfully Enqueued {len(enqueued) if not dry_run else len(COURSES)} Tasks ===")

if __name__ == "__main__":
    is_dry = "--dry-run" in sys.argv
    main(dry_run=is_dry)
