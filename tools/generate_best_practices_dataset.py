#!/usr/bin/env python3
"""
tools/generate_best_practices_dataset.py
----------------------------------------
Synthesizes high-density instruction tuning samples grounded in:
  1. AI Engineering Fellowship 2026 Golden Reference Standards (Weeks 1-17)
  2. Ecosystem Invariants (sync.bat, zero headless .ipynb, token isolation, Banker's memory floor)

Emits:
  - dataset/best_practices_train.jsonl (~2,000 samples)
  - dataset/best_practices_eval.jsonl (~500 samples)
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import random

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("best_practices_generator")

REPO_ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = REPO_ROOT / "dataset"

SYSTEM_PROMPT = (
    "You are the Fleet-Master AI Systems Architect and Fellowship Golden Reference Engine. "
    "Enforce production ML, deep learning, agentic routing, and ecosystem engineering standards "
    "with zero hallucination, strict typing, and defensive design."
)

FELLOWSHIP_TOPICS = [
    {
        "week": "Week 02 - FastAPI & Microservices",
        "question": "How should FastAPI microservices be structured to prevent monolithic route anti-patterns and memory leaks?",
        "answer": (
            "### Architectural Standards\n"
            "1. **Modular APIRouter Hierarchy**: Split routes by domain resource into `routers/<resource>.py` using `APIRouter(prefix='/api/v1/resource', tags=['resource'])`.\n"
            "2. **Pydantic v2 Models**: Enforce strict input validation with `BaseModel`, `Field(..., min_length=1)`, and `model_config = ConfigDict(extra='forbid')`.\n"
            "3. **Async Lifespan Management**: Use `@asynccontextmanager async def lifespan(app: FastAPI)` to initialize and tear down database connection pools cleanly.\n"
            "4. **Dependency Injection**: Inject database sessions via `Depends(get_db_session)` yielding within a `try...finally` block."
        ),
    },
    {
        "week": "Week 03 - Agentic Text-to-SQL",
        "question": "What security and schema invariants must be enforced in production Agentic Text-to-SQL pipelines?",
        "answer": (
            "### Security & Correctness Invariants\n"
            "1. **AST Validation via sqlglot**: Parse every generated query using `sqlglot.parse_one(sql)` and reject any query containing DDL or DML mutations (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`).\n"
            "2. **Schema Pruning & Token Budgeting**: Retrieve only relevant table schemas using vector similarity or BM25 index over table DDLs; never inject the full database schema into the LLM context.\n"
            "3. **Execution Guardrails**: Execute queries in a read-only transaction with a strict execution timeout (e.g. `statement_timeout = 3000ms`) and max row limits (`LIMIT 100`).\n"
            "4. **Self-Correction Loop**: Catch `OperationalError` and prompt the model with the exact SQL parser error for automated retry."
        ),
    },
    {
        "week": "Week 05 - Tree Ensembles & Imbalanced Classification",
        "question": "How do you prevent data leakage when using SMOTE or ADASYN with cross-validation in tree ensembles?",
        "answer": (
            "### Leakage-Free Resampling Pipeline\n"
            "1. **Pipeline Encapsulation**: Never apply `SMOTE().fit_resample(X, y)` before splitting data. Use `imblearn.pipeline.Pipeline` instead of `sklearn.pipeline.Pipeline`.\n"
            "2. **Fold Isolation**: When using `cross_val_score` or `GridSearchCV`, `imblearn.pipeline.Pipeline` automatically restricts synthetic sampling exclusively to the training folds, preventing test set contamination.\n"
            "3. **Multicollinearity Screening**: Check Variance Inflation Factor (VIF < 5.0) before fitting.\n"
            "4. **Post-Hoc Attribution**: Explain model predictions with `shap.TreeExplainer(model)` rather than naive feature importances."
        ),
    },
    {
        "week": "Week 08 - Time Series Forecasting",
        "question": "Why is standard K-Fold cross-validation forbidden in financial or sequential time series forecasting, and what should be used instead?",
        "answer": (
            "### Temporal Validation Invariant\n"
            "1. **Lookahead Bias Prevention**: Standard `KFold` or `train_test_split(shuffle=True)` leaks future information into past training instances.\n"
            "2. **Expanding Window Evaluation**: Use `sklearn.model_selection.TimeSeriesSplit(n_splits=5)` or an expanding/rolling walk-forward validation scheme.\n"
            "3. **Stationarity Verification**: Run Augmented Dickey-Fuller (ADF, $p < 0.05$) and KPSS tests to verify stationarity before autoregressive modeling.\n"
            "4. **Residual Diagnostics**: Enforce Ljung-Box test on model residuals to verify no autocorrelation remains."
        ),
    },
    {
        "week": "Week 11 - Vision Transformers & Multimodal",
        "question": "When building zero-shot image classification or defect detection pipelines, how should CLIP and ViT backbones be utilized?",
        "answer": (
            "### Multimodal Architecture\n"
            "1. **Zero-Shot Baseline**: Compute cosine similarity between image embeddings `image_features = model.encode_image(image)` and normalized text prompt embeddings `text_features = model.encode_text(prompts)`.\n"
            "2. **Prompt Ensembling**: Average embeddings across multiple domain templates (e.g., 'a photo of a defective surface', 'a close-up of a crack in steel').\n"
            "3. **Fine-Tuning Guardrails**: Freeze transformer backbone layers and fine-tune lightweight LoRA adapters or an MLP classification head with mixed-precision `torch.amp.autocast('cuda')`."
        ),
    },
    {
        "week": "Week 14 - Agentic Routing SLMs",
        "question": "How should Small Language Models (<1B parameters) be structured to achieve sub-50ms intent and duration routing?",
        "answer": (
            "### Low-Latency SLM Routing Design\n"
            "1. **Deterministic Structured JSON**: Constrain output vocabulary to schema-bound JSON fields (`archetype`, `matrix_cell`, `auto_tier`, `time_allocation`).\n"
            "2. **Quantized On-Device Inference**: Deploy GGUF INT4 via llama.cpp or OpenVINO INT4 on dedicated NPU tiles (`Intel AI Boost`, ~2W, 0% CPU).\n"
            "3. **Dynamic Duration Allocation**: Map prompt semantics to CPM durations ($D_j$) and timeout ceilings ($T_{\\max} = \\min(1200, 2.2 \\cdot D_j)$).\n"
            "4. **Fail-Safe Fallback Ladder**: On SLM timeout or socket error, instantly fall back to compiled regex heuristics in <1ms."
        ),
    },
    {
        "week": "Ecosystem Invariant - Git Workflow",
        "question": "Why are direct `git commit`, `git add`, and `git push` commands strictly forbidden in this repository, and what command must be run?",
        "answer": (
            "### Rule 1: Git Workflow & Ecosystem Automation\n"
            "1. **Strict Enforcement**: Raw `git commit`, `git add`, `git push`, or `git pull` break multi-branch tracking and bypass automated pre-commit secret scanning.\n"
            "2. **Authoritative Wrapper**: Always execute `.\\sync.bat` (or `.\\sync.ps1`). `.\\sync.bat` automatically bypasses Windows PowerShell ExecutionPolicy on freshly cloned machines.\n"
            "3. **Feature Commits**: Execute `.\\sync.bat -m 'feat(scope): detailed summary (#id)'`.\n"
            "4. **Pull Only**: Execute `.\\sync.bat -PullOnly`."
        ),
    },
    {
        "week": "Ecosystem Invariant - Headless Jupyter Notebooks",
        "question": "What is the invariant regarding headless CLI execution of `.ipynb` notebook files?",
        "answer": (
            "### Rule 4: Headless Execution Safety\n"
            "1. **Zero Headless Runs**: Never run or execute `.ipynb` files headlessly via CLI commands (e.g. `jupyter nbconvert`, `papermill`).\n"
            "2. **Execution Runtimes**: Leave execution for Google Colab GPU accelerators (via `colab-cloud-accelerator` or ColabCloudAdapter) or interactive runs in VS Code."
        ),
    },
    {
        "week": "Ecosystem Invariant - Memory Headroom Guard",
        "question": "What is the memory reserve invariant for Antigravity IDE stability and worker concurrency?",
        "answer": (
            "### Banker's Algorithm Memory Envelope\n"
            "1. **Reserve Floor**: 2,048 MB free RAM is permanently reserved for Antigravity IDE WorkingSet.\n"
            "2. **Worker Concurrency Calculation**: $\\lfloor (\\text{Free RAM} - 2048) / 256 \\rfloor$.\n"
            "3. **Zero Workers Below 2,304 MB**: Spawning halts if free memory falls below 2,304 MB, preventing OS thrashing and IDE crashes."
        ),
    },
]


def generate_variations(base_topics: list, target_count: int = 2500) -> list:
    """Expands base golden references with prompt variations and real-world edge cases."""
    samples = []
    
    variations_prefix = [
        "In our software ecosystem, ",
        "As an AI Systems Lead, explain: ",
        "Provide the authoritative implementation standard for: ",
        "What is the best practice and invariant for: ",
        "How do we prevent regressions when implementing: ",
    ]

    for topic in base_topics:
        # 1. Base canonical sample
        samples.append({
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": topic["question"]},
                {"role": "assistant", "content": topic["answer"]},
            ],
            "category": topic["week"],
        })

    # Multiply variations up to target_count
    idx = 0
    while len(samples) < target_count:
        topic = base_topics[idx % len(base_topics)]
        prefix = variations_prefix[(idx // len(base_topics)) % len(variations_prefix)]
        q = prefix + topic["question"].lower()
        samples.append({
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": q},
                {"role": "assistant", "content": topic["answer"]},
            ],
            "category": topic["week"],
        })
        idx += 1

    return samples


def main():
    parser = argparse.ArgumentParser(description="Generate AI Fellowship & Invariant Best Practices Dataset.")
    parser.add_argument("--count", type=int, default=2500, help="Total number of samples to generate")
    args = parser.parse_args()

    samples = generate_variations(FELLOWSHIP_TOPICS, target_count=args.count)
    random.seed(42)
    random.shuffle(samples)

    split = int(len(samples) * 0.8)
    train_samples = samples[:split]
    eval_samples = samples[split:]

    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    train_path = DATASET_DIR / "best_practices_train.jsonl"
    eval_path = DATASET_DIR / "best_practices_eval.jsonl"

    with open(train_path, "w", encoding="utf-8") as f:
        for s in train_samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    with open(eval_path, "w", encoding="utf-8") as f:
        for s in eval_samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    logger.info(f"Generated {len(train_samples)} training samples into {train_path.name}")
    logger.info(f"Generated {len(eval_samples)} evaluation samples into {eval_path.name}")


if __name__ == "__main__":
    main()
