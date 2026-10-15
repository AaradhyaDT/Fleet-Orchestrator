# Corrected approval note

Correction: the upgraded model artifact is `data/processed_sisfall/model/spark_cnn_int8_upgraded.tflite`, not a generically named `upgraded.tflite`.

I read the artifact and decoded `spark_cnn_model` from `firmware/main/models/spark_cnn_int8.h` (array declaration at lines 8–1585; declared length at line 1587). The two byte sequences are exactly equal: each is 18,912 bytes, with SHA-256 `dd0e8e3d6b201acba2b524a1f911958f70bf15a52bc6592eb5cec97e78d5a2ea`. This is direct artifact-identity evidence for the [[SPARK]] [[Human fall detection]] implementation.

Approval is limited to correcting the artifact identity. The byte comparison does not establish score provenance, model performance, or on-device validation; no such claim is made here. Human fall detection remains the primary scope; robotics is an exploratory future extension.
