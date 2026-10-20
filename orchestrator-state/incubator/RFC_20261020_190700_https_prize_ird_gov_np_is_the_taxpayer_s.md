# Incubator RFC: https://prize.ird.gov.np is the taxpayer's incentive program of Nepal

> **Raw Thought**: *"https://prize.ird.gov.np is the taxpayer's incentive program of Nepal Government. But as citizens, uploading it is fine but the coupon we receive says to 'Claim after verification - If your prize coupon is selected as a winner, submit the required details and a photo of the bill so the prize claim can be verified and processed.' . Now the problem has become managing all that photos bills and coupons whilst tracking which bill got the lottery win. I want to just click photo to give copyable details that we can paste and after submitting the info and downloading the coupon, we can store both for quick retrieval and lookup to see if our coupon matches the winner."*
> **Captured At**: `2026-10-20T13:22:37.457338+00:00`
> **Vault ID**: `VLT-20261020132159`

---

## 1. Executive Summary & Problem Formulation
The Government of Nepal’s taxpayer incentive and lottery program (`prize.ird.gov.np`) suffers from a critical friction point in the citizen-side record-keeping workflow: manual decoupling of physical/digital tax bills, generated coupon identifiers, and asynchronous winning-status verification. Citizens are forced to manually manage unstructured galleries of bill photos, text-based coupon codes, and PDF/image downloads without an automated cross-referencing mechanism. This RFC proposes the design and deployment of an intelligent, local-first OCR and relational receipt-to-coupon reconciliation engine. By automating zero-shot text extraction, deterministic coupon-to-bill metadata binding, and local state persistence, the system eliminates human error, prevents missed lottery claims, and establishes real-time winner verification mapping.

## 2. Target Ecosystem Module & Universe Mapping
- **Primary Repository / Module**: SPARK & Cyber-Forensics (Document Intelligence & Data Extraction Pipeline)
- **Universe Lobe**: U7 Cyber Resilience & U12 Civic-Tech Automation
- **Architectural Layer**: Client-Side Edge OCR, Local Relational State-Store, and Asynchronous Web-Scraping Verification Gate

## 3. Theoretical Invariant & Mathematical Model
Let a tax transaction record be defined as a tuple $T = (B_{img}, C_{id}, V_{status}, \tau)$, where $B_{img}$ is the raw bill image, $C_{id}$ is the unique coupon identifier, $V_{status} \in \{\text{Pending}, \text{Won}, \text{Lost}\}$ is the verification state, and $\tau$ is the transaction timestamp. 

We define the system’s primary state invariant as **Bijective Traceability**:
$$\forall C_{id}, \exists! B_{img} \quad \text{such that} \quad \mathcal{H}(B_{img}) \cap \mathcal{M}(C_{id}) \neq \emptyset$$
Where $\mathcal{H}$ represents the OCR text-extraction mapping function and $\mathcal{M}$ represents the metadata schema matching function. 

The verification control constraint using a Safety Barrier Function $h(x)$ ensuring no winning coupon is dropped:
$$h(x) = \text{Match}(C_{id}, \text{OfficialWinnerList}) - \text{Actioned}(C_{id}) \geq 0$$
If $h(x) == 0$ upon a winning match, an immediate interrupt flag $\xi_{alert}$ is triggered for user notification.

## 4. Falsifiable Hypothesis & Empirical Benchmark
- **Hypothesis**: Automating the ingestion of IRD tax bills via client-side edge OCR combined with local relational indexing will reduce coupon-to-bill lookup failure rates to 0% and decrease administrative tracking time per submission by $\geq 85\%$ compared to manual gallery management.
- **Verification Metric**: OCR character error rate (CER) $< 1.5\%$ on Nepali/English fiscal receipts; 100% relational integrity between downloaded coupon PDFs and source bill images; zero missed winning notifications during automated weekly rollouts.
- **Baseline Comparison**: Status quo (manual smartphone photo galleries, scattered text files, and manual checking of winner rolls) vs. proposed single-click capture, structured clipboard auto-population, and local indexed database lookup.

## 5. Failure Modes & Boundary Conditions
- **Edge Case 1**: Sub-optimal lighting, thermal paper fading, or non-standard formatting on physical tax bills leading to low OCR confidence scores.
- **Edge Case 2**: Changes in the DOM structure or API endpoints of the `prize.ird.gov.np` portal breaking automated submission helpers or winner-list scraping scripts.
- **Edge Case 3**: Local storage corruption or accidental cache clearing resulting in loss of cryptographic references to downloaded coupon files.

## 6. Immediate Next Step
- [ ] Initialize the local-first prototype repository structure featuring a client-side Tesseract/WebAssembly OCR wrapper and an SQLite schema designed to bind bill images, extracted metadata, and downloaded coupon artifacts.
