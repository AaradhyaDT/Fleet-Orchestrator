# SPARK thesis scout: implementation status and evidence

Grounded in [[SPARK]] and [[Human fall detection]] evidence. This note classifies findings as measured artifact results, historical reported values, estimates, or planned work.

## Executive summary

- Human-fall detection is the primary validated scope. The repo repeatedly frames SPARK as a human-gait clinical monitoring system, with robotics described as an architectural extension rather than a measured deployment target (`AGENT.md:3`, `AGENT.md:11`, `CLAUDE.md:4`, `README.md:5`).
- The strongest offline model evidence in the repo is a held-out SisFall evaluation with AUC-ROC = 0.9185 and sensitivity = 0.8781 in the generated test artifact (`data/processed_sisfall/model/test_report.txt:3-12`).
- The project headline values are still 87.81% sensitivity and 0.9185 AUC-ROC, but these are not the only recent metrics. The latest October 12 Colab run reports safety-threshold sensitivity 0.8981 and AUC-ROC 0.9272, while the archived model artifact retains 0.8781 / 0.9185 (`training/colab_run_output.txt:150-159`, `data/processed_sisfall/model/model_config.json:22-32`).
- The repo does not show a validated deployment result: physical hardware bring-up, Nepal cohort data collection, and on-device ESP32-S3 inference remain pending or unstarted (`README.md:155-160`, `README.md:66-68`, `AGENT.md:25`).

## 1) Primary scope and project framing

The repository is explicitly about human fall detection. The architecture description calls SPARK a “two-layer gated fall detection ... system” validated on human gait for clinical elderly monitoring, then notes extensibility to out-of-band bipedal robotic safety modules as a separate use case (`AGENT.md:3`, `AGENT.md:11`, `CLAUDE.md:4`, `README.md:5`).

This matters because robotics is framed as a future extension, not a real measured deployment target. The project tracker marks Nepal cohort trials, hardware validation, and Layer 3 mobile display client as not started (`README.md:66-68`, `README.md:155-160`).

## 2) Data provenance and artifact inventory

Dataset and model artifacts are present in two relevant locations:

- `data/processed_sisfall/` contains processed SisFall windows and model artifacts, including `windows.npy`, `labels.npy`, `meta.csv`, and `model/test_report.txt`, `model/model_config.json`, `model/quantization_report.txt`, `model/spark_cnn.keras`, `model/spark_cnn_int8.tflite`, and `model/spark_cnn_int8.h` (`data/README.md:15-18`, zip manifest for `data/SPARK_dataset_and_models.zip`).
- `data/SPARK_dataset_and_models.zip` contains a 13-item archive with the same core training and model artifacts, including `data/windows.npy`, `data/labels.npy`, `data/meta.csv`, `model/model_config.json`, `model/test_report.txt`, `model/quantization_report.txt`, `model/spark_cnn.keras`, `model/spark_cnn_int8.h`, and `model/spark_cnn_int8.tflite` (archive manifest inspected without extraction).

The processed data description also states 38,426 windows of shape `(200 × 6)` (`data/README.md:16-18`, `training/data_prep/prepare_sisfall.py:42`). The code comments and training loader confirm the canonical input tensor is `(N, 200, 6)` (`training/train_cnn.py:66`).

## 3) Historical values vs. current measured values

### Historical reported values

The project documentation repeatedly reports the milestone values:

- “1D CNN trained on SisFall with subject-grouped isolation (0.9185 AUC-ROC, 87.81% sensitivity)” (`README.md:148`).
- The supervisor report states: “subject-grouped, zero-data-leakage cross-validation scheme (87.81% sensitivity, 0.9185 AUC-ROC)” (`docs/SPARK_SUPERVISOR_PROGRESS_REPORT.md:29`).
- Older tracker notes record the same numbers (`dev_logs/SPARK_TRACKER.md:64`).

These are historical project claims and should be classified as milestone-reported values, not necessarily the latest run output.

### Measured artifact results from the latest run

The latest run in `training/colab_run_output.txt` is dated “Mon Oct 12 2026” and reports:

- 38,426 total windows, shape `(200, 6)` (`training/colab_run_output.txt:37-40`).
- Augmented training set size = 126,856 (`training/colab_run_output.txt:45`).
- Held-out evaluation matrix: sensitivity 0.8057 at default threshold, 0.7390 at Youden threshold, and 0.8981 at the safety-constrained threshold; AUC-ROC remains 0.9272 (`training/colab_run_output.txt:150-159`).

The generated artifact under `data/processed_sisfall/model/test_report.txt` is even more explicit:

- Test set: 6,712 windows (1,575 FALL, 5,137 NON_FALL) (`data/processed_sisfall/model/test_report.txt:3-4`).
- Optimal threshold (Youden’s J on validation): 0.3919 (`data/processed_sisfall/model/test_report.txt:5`).
- Sensitivity 0.8781, specificity 0.7818, F1 = 0.6781, AUC-ROC = 0.9185 (`data/processed_sisfall/model/test_report.txt:8-12`).

`model_config.json` preserves the same AUC-ROC and reports the safety-constrained threshold 0.4065 giving sensitivity 0.8981 (`data/processed_sisfall/model/model_config.json:3-32`).

Conclusion: the historical 87.81% / 0.9185 values are consistent with the archived model artifact; however, the latest Colab run reports a different safety-threshold evaluation and a slightly higher AUC-ROC. The repo contains both historical milestone reporting and current artifact output, so the values are not fully identical in provenance.

## 4) Input-shape contradiction: 200Hz × 3s vs. 200 × 6

There is a real contradiction in how the repo describes the input window.

- Architecture documentation says the MCU model evaluates a “200 Hz 3-second motion window (200 × 6)” (`AGENT.md:11`).
- `prepare_sisfall.py` says the native SisFall trial is 200 Hz, then it is explicitly downsampled to 100 Hz, and the default processed windows are 200 samples at 100 Hz, i.e. a 2-second window after resampling (`training/data_prep/prepare_sisfall.py:10-11`, `training/data_prep/prepare_sisfall.py:30-32`, `training/data_prep/prepare_sisfall.py:55-57`, `training/data_prep/prepare_sisfall.py:206-207`).
- The actual model/interface contract is `windows.npy` shape `(N, 200, 6)`, and the firmware contract is `kWindowSamples = 200`, `kChannelsPerSample = 6` (`training/train_cnn.py:66`, `firmware/main/tflite/inference.h:21-23`, `firmware/main/tflite/inference.h:35-36`).

Resolution: the canonical processed ML input is `(200, 6)`, not a raw 200 Hz × 3-second sample stream. The 3-second wording appears to be an acquisition or architectural intent, but the actual preprocessing code produces a 200-sample, 100 Hz window, which is 2 seconds. The repo therefore contains both a raw acquisition design statement and a processed-window data definition; they are not equivalent.

## 5) Model and firmware status

### Model status

The model architecture is a 1D CNN defined in `training/train_cnn.py`, matching the generated Colab output (`training/colab_run_output.txt:54-73`, `training/train_cnn.py:242-257`). The final trained Keras model and quantized TFLite model are present in the processed artifacts (`data/processed_sisfall/model/model_config.json:1-10`, `data/processed_sisfall/model/quantization_report.txt:4-23`).

The quantization report states:

- Keras FP32 size: 154,311 bytes,
- TFLite INT8 size: 18,904 bytes,
- flash target pass for <=120 KB,
- input tensor shape `[1, 200, 6]`, output tensor `[1, 2]`, AUC-ROC 0.9185 FP32 vs 0.8717 INT8 (`data/processed_sisfall/model/quantization_report.txt:4-33`).

### Firmware status

The firmware stub is present and documents the same interface contract: 200 samples × 6 channels, float32 input/output at the API boundary, with TFLite Micro model loading intentionally left as a stub (`firmware/main/tflite/inference.h:1-36`). There is no evidence of a successful real-device inference validation in the repo. The project tracker explicitly says hardware validation and on-hardware BLE/Layer 1 testing remain to be done (`README.md:155-160`, `README.md:66-68`).

## 6) Missing evidence and deployment gaps

Important missing evidence remains:

- No real cohort data collection has executed; the tracker marks Nepal cohort trials as not started (`README.md:68`).
- No physical hardware bring-up or bench verification is recorded; hardware delivery and on-hardware validation are still pending (`README.md:155-160`).
- No real end-to-end ESP32-S3 inference or BLE event validation is present; the firmware is stubbed (`firmware/main/tflite/inference.h:1-36`).
- Although the gateway service exists (`gateway/main.py`), there is no repository evidence of a validated hardware-to-gateway event loop beyond replay/mock pipelines.

## 7) Final assessment

Measured artifact results in the repo support a solid offline SisFall benchmark, but they do not yet support a claim of real-world deployability. The best-supported empirical statement is: a subject-grouped SisFall CNN achieved an AUC-ROC near 0.9185 and a sensitivity in the 87.81% range, while the latest safety-threshold run reported 0.8981 sensitivity and 0.9272 AUC-ROC in one artifact. The repo therefore contains both offline benchmark evidence and a pending deployment pipeline.

The strongest evidence alignment is:

- primary use case: human fall detection (`AGENT.md:3`, `CLAUDE.md:4`, `README.md:5`)
- robotics: exploratory / architectural extension, not measured deployment (`docs/CHANGELOG.md:21-26`, `README.md:5`)
- hardware/cohort status: pending or unstarted (`README.md:155-160`, `README.md:66-68`)
- model artifact: offline benchmark exists, deploy validation missing (`data/processed_sisfall/model/test_report.txt:3-12`, `firmware/main/tflite/inference.h:1-36`)
