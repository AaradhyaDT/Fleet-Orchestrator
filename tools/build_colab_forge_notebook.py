#!/usr/bin/env python3
"""
tools/build_colab_forge_notebook.py
-----------------------------------
Generates the authoritative Google Colab A100 training notebook for
fine-tuning Qwen2.5-Coder-3B-Instruct (Daily Driver v2) using Unsloth
on the unified fleet dataset. Exports versioned _v2 GGUF Q4_K_M and
OpenVINO INT4 artifacts with evaluation loss logging.

v2 Changes (tracked under #19):
  - Deactivated Phase 2 (7B Powerhouse) to save compute units
  - Added trainer.evaluate() for eval loss logging
  - Versioned output artifacts with _v2 suffix
  - Validation cell uses 3B model directly
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = ROOT / "notebooks" / "fleet_master_brain_forge.ipynb"
ALIAS_OUTPUT = ROOT / "notebooks" / "slm_time_router_forge.ipynb"

nb = {
    "nbformat": 4,
    "nbformat_minor": 0,
    "metadata": {
        "colab": {
            "provenance": [],
            "authorship_tag": "ABX9TyP/Aaradhya-Fleet",
            "include_colab_link": True,
            "gpuType": "A100"
        },
        "kernelspec": {
            "name": "python3",
            "display_name": "Python 3"
        },
        "language_info": {
            "name": "python"
        },
        "accelerator": "GPU"
    },
    "cells": []
}

def add_md(text):
    nb["cells"].append({
        "cell_type": "markdown",
        "metadata": {},
        "source": [line + "\n" for line in text.strip().split("\n")]
    })

def add_code(code):
    nb["cells"].append({
        "cell_type": "code",
        "metadata": {},
        "execution_count": None,
        "outputs": [],
        "source": [line + "\n" for line in code.strip().split("\n")]
    })

add_md(r"""# Fleet Master Brain v2 Forge: Qwen2.5-Coder-3B Daily Driver (Colab A100 SXM4)

This notebook fine-tunes **`Qwen2.5-Coder-3B-Instruct`** (Daily Driver v2, ~2.1 GB GGUF) using **Unsloth** LoRA on an **NVIDIA A100 GPU** with **High RAM**.

> **v2 Changes**: Eval loss logging via `trainer.evaluate()`, versioned `_v2` output artifacts, 7B Powerhouse deferred.

### Governed by Ecosystem Standards:
* **`adaptive-workflow`**: Context firebreak, 2D matrix routing, mathematical CPM durations ($D_j$), dynamic queue worker timeouts.
* **`slm-router-forge`**: Strict ChatML formatting, SFT compatibility bridge (`INV-SLM-07`), zero-noise INT4 GGUF quantization, and direct Google Drive export (`INV-SLM-04`).

### Unified Multi-Task Ingestion:
1. **Task Time & Intent Allocation**: Discretized tiers (`T0`–`T4`), integer seconds, dynamic timeout ceiling ($\max(30, 2.2 \times D)$), and CPM duration weights.
2. **Agent-Reflex Self-Healing Recovery**: `[Tool Failure + Traceback] -> [Diagnosis + Fix]`.
3. **Tool Speculation DAGs**: Multi-step action sequences from user prompts.
4. **Copilot Mistake Counter-Dataset**: Verified corrections for low-cost auto-tier regressions and syntax bugs.
5. **AI Fellowship & Ecosystem Invariants**: 17-week golden reference standards (FastAPI, SMOTE, TimeSeriesSplit, ViT, sqlglot) + repository invariants.
6. **Cross-IDE Developer Transcripts**: Real-world multi-turn in-editor interactions from VS Code Copilot Chat, OpenCode Desktop, Claude Sonnet exports, and Brainstorm research archives.""")

add_code("""# ==========================================
# CELL 1: Environment Setup & Hardware Audit
# ==========================================
!pip install --upgrade --no-cache-dir "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"
!pip install --no-deps unsloth_zoo bitsandbytes accelerate peft trl triton

import os, gc, shutil, json, hashlib
import torch

gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU"
vram_gb = round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 2) if torch.cuda.is_available() else 0
print(f"\\n[HARDWARE ACCELERATOR] {gpu_name} ({vram_gb} GB VRAM)")
print(f"[BF16 SUPPORT] {torch.cuda.is_bf16_supported()}")

if vram_gb < 15:
    print("[WARNING] Running on low VRAM. Ensure batch size is conservative.")
else:
    print("[STATUS] A100 / High-VRAM Detected. Splurge parameters unlocked!")""")

add_code("""# ==========================================
# CELL 2: Google Drive Mount & Unified Dataset Ingestion
# ==========================================
from google.colab import drive
from datasets import load_dataset

# Ensure gdown is available for Drive file retrieval
import subprocess
subprocess.run(["pip", "install", "-q", "gdown"], check=False)

# Mount Google Drive for automatic persistence
if not os.path.exists('/content/drive/MyDrive'):
    drive.mount('/content/drive')

DRIVE_TARGET_DIR = "/content/drive/MyDrive/Share to Aaradhya/Super-NLM/Fleet-Orchestrator"
os.makedirs(DRIVE_TARGET_DIR, exist_ok=True)

# Locate dataset: Check local directory, mounted Drive, or auto-fetch via File ID
train_file = "unified_fleet_train.jsonl"
eval_file = "unified_fleet_eval.jsonl"

for fname in [train_file, eval_file]:
    if not os.path.exists(fname):
        drive_candidate = os.path.join(DRIVE_TARGET_DIR, fname)
        if os.path.exists(drive_candidate):
            print(f"Loading {fname} directly from mounted Google Drive...")
            shutil.copy(drive_candidate, fname)
        else:
            print(f"Auto-fetching {fname} via Google Drive File ID...")
            fid = "1Q3O5pUmJ5A4pZ2Gg5DUMoVHQEz2v-YWA" if "train" in fname else "1EzcECUxPHsCMZ4jkTFT6gwQ75YHq5ztU"
            if fid:
                subprocess.run(["gdown", f"https://drive.google.com/uc?id={fid}", "-O", fname])

assert os.path.exists(train_file), f"Dataset file {train_file} could not be retrieved automatically!"

raw_train = load_dataset("json", data_files=train_file, split="train")
raw_eval = load_dataset("json", data_files=eval_file, split="train") if os.path.exists(eval_file) else None

def format_prompts(batch):
    \"\"\"Handle both Alpaca (instruction/input/output) and ChatML (messages) schemas.\"\"\"
    texts = []
    n = len(batch[list(batch.keys())[0]])
    for i in range(n):
        # Check if this record uses the ChatML messages schema
        if "messages" in batch and batch["messages"][i] is not None:
            msgs = batch["messages"][i]
            sys_content = ""
            user_content = ""
            asst_content = ""
            for msg in msgs:
                if msg["role"] == "system":
                    sys_content = msg["content"]
                elif msg["role"] == "user":
                    user_content = msg["content"]
                elif msg["role"] == "assistant":
                    asst_content = msg["content"]
            text = f"<|im_start|>system\\n{sys_content}<|im_end|>\\n<|im_start|>user\\n{user_content}<|im_end|>\\n<|im_start|>assistant\\n{asst_content}<|im_end|>"
        else:
            # Standard Alpaca format: instruction/input/output
            inst = batch["instruction"][i]
            inp = batch["input"][i]
            out = batch["output"][i]
            text = f"<|im_start|>system\\n{inst}<|im_end|>\\n<|im_start|>user\\n{inp}<|im_end|>\\n<|im_start|>assistant\\n{out}<|im_end|>"
        texts.append(text)
    return {"text": texts}

formatted_train_dataset = raw_train.map(format_prompts, batched=True, remove_columns=raw_train.column_names)
formatted_eval_dataset = raw_eval.map(format_prompts, batched=True, remove_columns=raw_eval.column_names) if raw_eval else None
print(f"\\n[DATASET READY] {len(formatted_train_dataset)} train samples, {len(formatted_eval_dataset) if formatted_eval_dataset else 0} eval samples loaded!")""")

add_code("""# ==========================================
# CELL 3: SFT Compatibility Bridge & Imports (INV-SLM-07)
# Enforces Unsloth import precedence and trl/transformers compatibility
# ==========================================
import unsloth
from unsloth import FastLanguageModel

# Import trl and transformers after unsloth to ensure all memory optimizations are applied
from trl import SFTTrainer, SFTConfig
from transformers import TrainingArguments, Trainer

# SFT Compatibility Bridge: ensure tokenizer and processing_class interop
_orig_trainer_init = Trainer.__init__
def _patched_trainer_init(self, *args, **kwargs):
    if "tokenizer" in kwargs and "processing_class" not in kwargs:
        tok = kwargs.pop("tokenizer")
        kwargs["processing_class"] = tok
        self.tokenizer = tok
    elif "tokenizer" in kwargs:
        self.tokenizer = kwargs.pop("tokenizer")
    return _orig_trainer_init(self, *args, **kwargs)
Trainer.__init__ = _patched_trainer_init

print("[BRIDGE READY] Unsloth FastLanguageModel & SFTTrainer initialized successfully!")""")

add_code("""# ==========================================
# CELL 4: Phase 1 -- Train Qwen2.5-Coder-3B v2 (Daily Driver)
# ~2.1 GB GGUF for laptop LM Studio with music/Antigravity running
# ==========================================
from unsloth import FastLanguageModel

print("\\n" + "="*60)
print("PHASE 1: TRAINING QWEN2.5-CODER-3B v2 (DAILY DRIVER)")
print("="*60)

max_seq_len = 4096
model_3b, tokenizer_3b = FastLanguageModel.from_pretrained(
    model_name = "unsloth/Qwen2.5-Coder-3B-Instruct-bnb-4bit",
    max_seq_length = max_seq_len,
    dtype = torch.bfloat16,
    load_in_4bit = True,
)

model_3b = FastLanguageModel.get_peft_model(
    model_3b,
    r = 64,
    target_modules = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    lora_alpha = 128,
    lora_dropout = 0,
    bias = "none",
    use_gradient_checkpointing = "unsloth",
    random_state = 3407,
)

trainer_3b = SFTTrainer(
    model = model_3b,
    tokenizer = tokenizer_3b,
    train_dataset = formatted_train_dataset,
    eval_dataset = formatted_eval_dataset,
    dataset_text_field = "text",
    max_seq_length = max_seq_len,
    dataset_num_proc = 4,
    packing = False,
    args = SFTConfig(
        per_device_train_batch_size = 4,
        gradient_accumulation_steps = 4,
        warmup_steps = 10,
        num_train_epochs = 3,
        learning_rate = 2e-4,
        bf16 = True,
        logging_steps = 25,
        optim = "adamw_8bit",
        weight_decay = 0.01,
        lr_scheduler_type = "cosine",
        seed = 3407,
        output_dir = "outputs_3b_v2",
        eval_strategy = "epoch",
        save_strategy = "epoch",
        dataset_text_field = "text",
        max_seq_length = max_seq_len,
    ),
)

train_stats = trainer_3b.train()
print(f"\\n[TRAIN] Training loss: {train_stats.training_loss:.4f}")
print(f"[TRAIN] Runtime: {train_stats.metrics['train_runtime']:.1f}s")

# Evaluation loop for v2 loss logging
if formatted_eval_dataset:
    eval_results = trainer_3b.evaluate()
    print(f"\\n[EVAL] Eval loss: {eval_results['eval_loss']:.4f}")
    print(f"[EVAL] Eval runtime: {eval_results.get('eval_runtime', 0):.1f}s")
else:
    print("\\n[EVAL] No eval dataset available, skipping evaluation.")

# Export INT4 GGUF (versioned _v2)
print("\\n[EXPORT] Quantizing 3B model to Q4_K_M GGUF (v2)...")
model_3b.save_pretrained_gguf("fleet_master_brain_3b_q4km_v2", tokenizer_3b, quantization_method="q4_k_m")

# Copy directly to Google Drive
gguf_3b_src = "fleet_master_brain_3b_q4km_v2/unsloth.Q4_K_M.gguf"
if not os.path.exists(gguf_3b_src):
    for root, dirs, files in os.walk("."):
        for f in files:
            if f.endswith(".gguf") and "3b" in root.lower() and "v2" in root.lower():
                gguf_3b_src = os.path.join(root, f)
                break
        if os.path.exists(gguf_3b_src):
            break
    # Fallback: find any GGUF with 3b in path
    if not os.path.exists(gguf_3b_src):
        for root, dirs, files in os.walk("."):
            for f in files:
                if f.endswith(".gguf"):
                    gguf_3b_src = os.path.join(root, f)
                    break
            if os.path.exists(gguf_3b_src):
                break

gguf_3b_dest = os.path.join(DRIVE_TARGET_DIR, "fleet_master_brain_3b_q4km_v2.gguf")
print(f"Persisting 3B v2 GGUF to Google Drive: {gguf_3b_dest}...")
shutil.copy(gguf_3b_src, gguf_3b_dest)
print(f"[SAVED] 3B v2 GGUF size: {round(os.path.getsize(gguf_3b_dest) / (1024**2), 1)} MB")

# Export OpenVINO INT4 IR Package for Intel Core Ultra NPU (versioned _v2)
print("\\n[EXPORT] Exporting 3B model to OpenVINO INT4 IR v2 for Meteor Lake NPU...")
try:
    import subprocess
    subprocess.run(["pip", "install", "-q", "optimum[openvino]"], check=True)
    merged_3b_dir = "fleet_master_brain_3b_merged_v2"
    model_3b.save_pretrained_merged(merged_3b_dir, tokenizer_3b, save_method="merged_16bit")
    ov_out_dir = "fleet_master_brain_3b_openvino_int4_v2"
    subprocess.run([
        "optimum-cli", "export", "openvino",
        "--model", merged_3b_dir,
        "--weight-format", "int4",
        "--sym",
        "--group-size", "128",
        "--task", "text-generation-with-past",
        ov_out_dir
    ], check=True)
    shutil.make_archive(ov_out_dir, "zip", ov_out_dir)
    ov_zip_dest = os.path.join(DRIVE_TARGET_DIR, "fleet_master_brain_3b_openvino_int4_v2.zip")
    shutil.copy(f"{ov_out_dir}.zip", ov_zip_dest)
    print(f"[SAVED] OpenVINO INT4 IR v2 ZIP persisted to: {ov_zip_dest}")
    shutil.rmtree(merged_3b_dir, ignore_errors=True)
except Exception as e:
    print(f"[NOTE] OpenVINO export status: {e}")""")


add_code("""# ==========================================
# CELL 5: Live Validation & Local LM Studio Instructions
# ==========================================
import json
FastLanguageModel.for_inference(model_3b)

test_prompt = "Fix the regression in test_warehouse_mem_sim.py where queue latency was calculating as zero."
prompt_text = f"<|im_start|>system\\nYou are the high-speed Intent, Skill, and Task Time Allocation Router for the Aaradhya development ecosystem. Classify the incoming user intent into the exact lifecycle archetype, tier, 2D matrix cell, primary skill, supporting skills, velocity profile, and task time allocation in strict JSON format.<|im_end|>\\n<|im_start|>user\\n{test_prompt}<|im_end|>\\n<|im_start|>assistant\\n"

inputs = tokenizer_3b([prompt_text], return_tensors = "pt").to("cuda")
outputs = model_3b.generate(**inputs, max_new_tokens = 220, use_cache = True)
res = tokenizer_3b.batch_decode(outputs)[0].split("<|im_start|>assistant\\n")[-1].replace("<|im_end|>", "").strip()

print("\\n[LIVE INFERENCE TEST OUTPUT (3B v2)]")
print(res)
try:
    parsed = json.loads(res)
    print("\\n[VALIDATION GATE] JSON parsing verified successfully!")
except Exception as e:
    print(f"\\n[VALIDATION WARNING] JSON output check: {e}")

print("\\n" + "="*60)
print("COMPLETE! 3B v2 MODEL PERSISTED TO GOOGLE DRIVE:")
print(f"  GGUF: {gguf_3b_dest}")
if 'ov_zip_dest' in dir():
    print(f"  OpenVINO: {ov_zip_dest}")
print("="*60)
print("\\nTo run locally in LM Studio on your laptop:")
print('lms import -c --user-repo aaradhya/fleet-master-3b-v2 -y "models/fleet_master_brain_3b_q4km_v2.gguf"')
print('lms server start')
print('lms load fleet-master-3b-v2 --identifier fleet-master-3b-v2 -y')""")

add_code("""# ==========================================
# CELL 6: Auto-Disconnect Runtime & Save Compute Units (INV-SLM-10)
# ==========================================
import time

print("[SUCCESS] Fleet Master Brain 3B v2 trained and persisted to Google Drive.")
print("[TEARDOWN] Releasing A100 VM to stop compute unit burn...")
time.sleep(5)

from google.colab import runtime
runtime.unassign()""")

if __name__ == "__main__":
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(nb, f, indent=2)
    with open(ALIAS_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(nb, f, indent=2)
    print(f"Successfully generated canonical {OUTPUT_FILE.name} and alias {ALIAS_OUTPUT.name} ({len(nb['cells'])} cells)")
