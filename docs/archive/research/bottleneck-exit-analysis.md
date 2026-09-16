# Bottleneck Exit Analysis: Direct-Seed Detection Failure Root Cause & Escape Plan

**Date:** 2026-04-14
**Status:** Analysis complete — no code changes made
**Scope:** Independent analysis of the direct-seed detection plateau, run in parallel with the hi-res retry batch in the other session

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Evidence Inventory](#2-evidence-inventory)
3. [Root Cause Analysis](#3-root-cause-analysis)
4. [Why Geometry & Activation Are Exhausted](#4-why-geometry--activation-are-exhausted)
5. [Why Hi-Res Retry May Also Miss](#5-why-hi-res-retry-may-also-miss)
6. [Attack Vector A: Model-Tier Upgrade](#6-attack-vector-a-model-tier-upgrade)
7. [Attack Vector B: Multi-Scale Ensemble](#7-attack-vector-b-multi-scale-ensemble)
8. [Attack Vector C: Player-Ranked Spatial Bridge](#8-attack-vector-c-player-ranked-spatial-bridge)
9. [Attack Vector Comparison Matrix](#9-attack-vector-comparison-matrix)
10. [Sequencing & Decision Framework](#10-sequencing--decision-framework)
11. [Anti-Goals](#11-anti-goals)
12. [Verification Plan](#12-verification-plan)
13. [Relationship to Existing Playbook](#13-relationship-to-existing-playbook)

---

## 1. Executive Summary

The football-analyst pipeline has been stuck at a stable plateau for multiple promoted proofs:

- `acceptedBallFrames = 101`
- `controlledPossessionFrames = 98`
- `ballTrackViable = false`
- `ballTrackEdgeFrameShare = 0.812`

Across **six consecutive sprints** — seed-centered funnel, true seed window, bounded anchor seed, seed-to-box context activation, player-biased context geometry, seed window hit-rate ladder — the proposal pipeline has been improved from zero activation to full activation, from bad geometry to player-biased expansion. **None of them produced a single direct-seed detection.**

This analysis concludes that:

> **The bottleneck is a model capability gap in YOLOv10n, not a pipeline geometry or activation problem.**

YOLOv10n (5.8M parameters, NMS-free architecture) cannot reliably detect a sports ball (COCO class 32) in small crops centered on the ball's actual location. It *can* detect balls in larger player-ranked crops because those provide scene context (players, field markings) that the COCO-pretrained model depends on.

Three structurally different escape vectors are proposed below, each attacking the root cause from a different angle.

---

## 2. Evidence Inventory

### 2.1 Stable plateau metrics (across all recent proofs)

| Metric | Value | Stable since |
|--------|-------|-------------|
| `acceptedBallFrames` | 101 | pod-first-proof-recovery sprint |
| `controlledPossessionFrames` | 98 | pod-first-proof-recovery sprint |
| `ballTrackViable` | false | all proofs |
| `ballTrackEdgeFrameShare` | 0.812 | all proofs |
| `eventFamilyCount` | 5 | all proofs |
| Selected cluster | 1 | all proofs |
| Winning recovery profile | `width_cap_075` | all proofs |

### 2.2 Proposal activation metrics (latest: player-biased-seed-context-geometry sprint)

| Metric | Value | Interpretation |
|--------|-------|---------------|
| `proposalCandidateFrames` | 111 | Proposals activate on nearly every seeded frame |
| `proposalWindowCount` | 333 | 3 windows per frame (seed tight + context + player ranked) |
| `proposalDirectSeedTightWindowFrames` | 111 | Tight seed windows fire on every seeded frame |
| `proposalDirectSeedContextWindowFrames` | 90 | Context windows activate broadly after activation fix |
| `proposalDirectSeedContextExpandedFrames` | 80 | Geometry expansion is working |
| `proposalDirectSeedContextMeanExpansionPx` | 57.71 | Average ~58px expansion toward seed |
| `proposalDirectSeedContextMeanSeedToBoxDistance` | 71.74 | Seed-to-player distance is well-bounded |
| `proposalPlayerRankedWindowFrames` | 111 | Player-ranked also fires every seeded frame |
| `proposalMeanWindowWidth` | 111.38 px | Average crop width across all window types |

### 2.3 Detection hit rates (latest: player-biased-seed-context-geometry sprint)

| Metric | Value | Status |
|--------|-------|--------|
| **`proposalDirectSeedDetectedFrames`** | **0** | ❌ Zero across all 6 sprints |
| **`proposalDirectSeedTightDetectedFrames`** | **0** | ❌ Never produced a hit |
| **`proposalDirectSeedContextDetectedFrames`** | **0** | ❌ Never produced a hit |
| **`proposalPlayerRankedDetectedFrames`** | **9** | ✅ Only surviving source |
| `proposalRawDetectedFrames` | 9 | All 9 from player-ranked |
| `proposalAfterSeedCollapseFrames` | 9 | All 9 survive collapse |
| `proposalAfterFalseBallSuppressionFrames` | 9 | All 9 survive filtering |

### 2.4 Recovery profile comparison (latest proof)

| Profile | Candidate frames | Selected frames | Viable |
|---------|-----------------|----------------|--------|
| `baseline_player_window` | 217 | 17 | ✅ |
| **`width_cap_075`** | **221** | **20** | **✅ (Winner)** |
| `width_cap_06` | 163 | 7 | ✅ |
| `crop_edge_margin_40` | 202 | 17 | ✅ |
| `upper_crop_band_075` | 77 | 7 | ✅ |
| `edge_margin_40_upper_075` | 73 | 7 | ✅ |
| `edge_margin_40_upper_078` | 96 | 7 | ✅ |
| `proposal_windows_075` | 9 | 9 | ✅ |
| `anchor_corridor_width_cap_075` | 0 | 0 | ❌ |

The winning profile is `width_cap_075` — a broad player-window crop — because it produces 20 selected frames vs the proposal profile's 9. The proposal profile loses selection because direct-seed windows contribute zero detections.

### 2.5 Sprint outcome history

| Sprint | Target | Outcome |
|--------|--------|---------|
| Seed-centered proposal funnel | Activation | `proposalCandidateFrames` went from 0 → nonzero. Direct-seed detections: **0** |
| True seed-centered proposal window | Geometry | Windows now center on seed. Direct-seed detections: **0** |
| Bounded anchor seed | Seed sourcing | Anchors propagate correctly. Direct-seed detections: **0** |
| Seed-to-box context activation | Activation | Context frames jumped 7 → 90. Direct-seed detections: **0** |
| Player-biased seed context geometry | Geometry | Expansion working, 80 frames expanded. Direct-seed detections: **0** |
| Seed window hit-rate ladder | Ranking | Ladder verified correct. Direct-seed detections: **0** |

---

## 3. Root Cause Analysis

### 3.1 The core finding

> **YOLOv10n cannot reliably detect a sports ball (COCO class 32) in small crops centered on the ball's actual location.**

This is a **model capability gap**, not a pipeline geometry problem.

### 3.2 Why player-ranked succeeds where direct-seed fails

**Player-ranked crops are larger and provide scene context:**

- A `player_ranked` window is built from a player's source bounding box with `proposal_crop_width_ratio=0.35` applied to the player's location
- When a player is near the ball, the resulting crop is effectively a "mini-scene" — the model sees a player body, pitch context, and sometimes a ball nearby
- YOLOv10n was trained on COCO dataset where sports balls appear *in context* (next to people, on fields, in sports scenes)
- This contextual information is what the model uses to anchor its detection confidence

**Direct-seed crops are small and context-free:**

- A `direct_seed_tight` window is built from `(seed_center_x, seed_center_y, seed_center_x, seed_center_y)` — a zero-size box centered on the ball's last known location
- After padding with `PLAYER_PROPOSAL_CROP_PADDING_PX = 24` and enforcing `MIN_PLAYER_PROPOSAL_CROP_WIDTH = 96`, the crop is only ~96–144px
- This crop contains almost exclusively grass and a tiny ball (8-20px diameter at broadcast camera distance)
- The ball occupies maybe 8-15% of the crop area
- This is wildly out-of-distribution for a model trained on natural images where objects occupy meaningful portions of the frame

### 3.3 The ball size problem

At typical broadcast football camera distances:
- A football is approximately **8–20 pixels** across in the source frame
- In a direct-seed crop of ~111px wide, the ball is **7–18% of the crop width**
- When this crop is resized to `imgsz=1600` for inference, the ball becomes ~112–288px in the inference tensor
- But the surrounding context is nothing but upscaled grass texture — no players, no field markings, no scene structure
- The detector has no contextual anchors to build confidence on

In contrast, in a player-ranked crop of ~672px wide:
- The same 8-20px ball is **1.2–3% of the crop width**
- But the crop also contains players (100-200px tall), field markings, and scene structure
- When resized to `imgsz=1600`, the ball is ~19–48px in the inference tensor
- The detector can use player proximity, field context, and scene structure to boost confidence

### 3.4 YOLOv10n architecture weakness

The project's own documentation (`improvements-2.txt` line 58) states:

> "The evolutionary step from YOLOv8 to YOLOv10 introduced revolutionary concepts, most notably Non-Maximum Suppression (NMS)-free training designed to reduce inference latency. However, this specific architectural choice inherently weakened the model's performance in dense, overlapping object scenarios."

This NMS-free architecture also weakens performance on **isolated small objects**. The NMS-free one-to-one head assignment means the model has fewer chances to "try" detecting a small object — it commits to a single prediction per anchor location rather than generating multiple overlapping candidates that NMS would later resolve.

### 3.5 The 5.8M parameter budget

YOLOv10n ("nano") has only 5.8M parameters. Its feature pyramid has limited capacity for small-object feature extraction. By contrast:
- YOLOv11s has 9.4M parameters and enhanced spatial attention for small objects
- YOLOv11m has 20.1M parameters
- Your Blackwell GPU has 32GB VRAM — it is dramatically underutilized by a nano model

---

## 4. Why Geometry & Activation Are Exhausted

The six sprint outcomes prove that the pipeline's proposal geometry and activation are no longer limiting factors:

### Activation is solved
- `proposalDirectSeedContextEligibleFrames = 90` (out of 111 seeded frames)
- `proposalDirectSeedTightWindowFrames = 111` (every seeded frame)
- Context activation jumped from 7 → 90 after the seed-to-box activation sprint

### Geometry is correct
- Player-biased expansion is working: 80/90 context frames expand toward the seed
- Average expansion is 57.71px — the crop is reaching toward the ball's location
- The seed-to-box distance of 71.74px is reasonable and well-bounded

### Ranking is correct
- The ladder (`direct_seed_context > direct_seed_tight > player_ranked`) is correctly implemented
- Pre-collapse tie-breaking is deterministic and well-tested
- 8 focused tests pass for the ladder behavior

### The evidence is clear
- Zero direct-seed detections across 6 sprints
- 9 player-ranked detections consistently surviving across every proof
- The same model, same confidence threshold, same classes — the only difference is crop size and content

**Further geometry or activation sprints cannot break this plateau.** The problem is downstream of where these sprints operate.

---

## 5. Why Hi-Res Retry May Also Miss

The other session is implementing a hi-res retry (`DIRECT_SEED_HI_RES_RETRY_IMGSZ = 960`) that re-runs inference on the same crop at a higher resolution when the base pass finds nothing.

### Why it's a valid diagnostic step
- It directly tests whether the detection failure is scale-dependent
- If it produces detections, the problem was simply wrong inference resolution
- It's cheap to implement and doesn't change the product contract
- The diagnostics it adds (`proposalDirectSeedHiResRetryFrames`, etc.) are permanently useful

### Why it may not break the plateau
1. **Same tiny crop, different scale.** If the crop is 111×111px, resizing it to 960px inference just upscales grass and a ~12px ball blob to a ~104px blob with heavy interpolation artifacts. The model has never seen training data that looks like this.

2. **The COCO-pretrained model needs scene context, not just resolution.** Making the ball bigger in the inference tensor doesn't add players, field markings, or scene structure. The model's learned features for "sports ball" include contextual cues that remain absent.

3. **The retry is still the same model.** YOLOv10n's limited feature pyramid and NMS-free architecture are the fundamental constraint. Running the same model at a different scale doesn't change its capability envelope — it just slides along the scale axis.

### Expected outcome
The hi-res retry is most likely to produce:
- `proposalDirectSeedHiResRetryFrames > 0` (it fires on every zero-detect seed frame)
- `proposalDirectSeedHiResRetryDetectedFrames = 0` (still no detections)
- This would confirm the model-capability hypothesis and trigger the pre-committed fallback

If the hi-res retry **does** produce detections, it means the ball was at a scale that the base resolution missed but 960 catches. In that case, the other session's approach wins and this analysis's attack vectors become backup options.

---

## 6. Attack Vector A: Model-Tier Upgrade

### Thesis
Replace YOLOv10n with a model that has better small-object recall. This directly addresses the root cause.

### Why this is the highest-expected-value lever

1. **The pipeline already works when the model can detect.** Player-ranked's 9 detections prove the entire proposal → collapse → recovery → truth layer chain is functional. The only broken link is model recall on small crops.

2. **Your own research recommends this.** `Guerilla Analytics_ Future Improvements.md` (line 69): "YOLOv11 integrates the C3k2 Block, a refined bottleneck module... YOLOv11 employs an enhanced spatial attention mechanism designed explicitly to identify small or partially occluded items."

3. **It's a drop-in replacement.** Same Ultralytics API, same `.predict()` call, same COCO classes. Zero code changes to `run_guerilla.py`.

4. **Your GPU is dramatically underutilized.** A 32GB Blackwell GPU running a 5.8M parameter nano model is like using a Formula 1 car to drive to the grocery store.

### Model candidates

| Model | Params | Key advantage | Inference speed (est.) | Drop-in? |
|-------|--------|---------------|----------------------|----------|
| **YOLOv11s** | 9.4M | C3k2 + spatial attention for small objects | ~1.0x vs v10n on Blackwell | ✅ Yes |
| **YOLOv11m** | 20.1M | Larger backbone, better recall | ~1.5x slower | ✅ Yes |
| YOLOv11l | 25.3M | Even larger, diminishing returns | ~2x slower | ✅ Yes |
| RT-DETR-l | 32M | Transformer, excellent small-object recall | ~2x slower, different API | ⚠️ Partial |
| Fine-tuned YOLOv10n | 5.8M | Same arch, learned your exact data distribution | 2-4h pod training cost | ✅ Yes |

### Recommended first attempt: YOLOv11s

**Why "s" not "m" or "l":**
- The jump from v10n (5.8M) to v11s (9.4M) is +62% parameters with specifically redesigned small-object attention
- Going to "m" (20.1M) adds 2x more parameters but the small-object attention is the same — it's a capacity increase, not an architecture change
- If "s" doesn't work, "m" is the natural escalation

### Implementation sketch

```
# On the pod — no code changes needed
wget https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11s.pt \
     -O /workspace/weights/yolo11s.pt

# Run the exact same proof loop with the new model
cd /workspace/fotball-analyst
source /workspace/fotball-venv/bin/activate
export QT_QPA_PLATFORM=offscreen
export YOLO_CONFIG_DIR=/workspace/.config/Ultralytics
export PYTHONPATH=/workspace/fotball-analyst

python backend/scripts/run_local_app_path_proof.py \
  --video-path /workspace/fotball-analyst/videos/trimed-5min.mp4 \
  --model-path /workspace/weights/yolo11s.pt
```

### Risks and mitigations

| Risk | Mitigation |
|------|-----------|
| More false positives from higher recall | Truth gates, edge filtering, and anchor support already exist unchanged |
| Different detection box sizes | The pipeline uses relative source boxes, not absolute sizes |
| Different confidence distributions | `TRACKING_CONF=0.12` and `BALL_RECOVERY_CONF=0.08` are already aggressive |
| Tracking ID continuity change | BoT-SORT tracker works independently of detector model |
| Inference speed increase | Negligible on 32GB Blackwell GPU |

### Expected diagnostic outcome

If the model-tier upgrade is the right lever:
- `proposalDirectSeedDetectedFrames` rises from 0 to some positive number
- `proposalDirectSeedTightDetectedFrames` may also become non-zero
- `proposalPlayerRankedDetectedFrames` likely stays ≥ 9 or increases
- `bestProposalSelectedFrames` increases, making `proposal_windows_075` competitive with `width_cap_075`
- Downstream: `acceptedBallFrames` increases, `ballTrackEdgeFrameShare` drops, `controlledPossessionFrames` rises

---

## 7. Attack Vector B: Multi-Scale Ensemble Inside Seed Windows

### Thesis
Instead of running inference once (or twice with hi-res retry), run the detector at 3 different scales on the same crop and union the results.

### Why it targets the root cause
The ball's apparent size inside the crop varies with camera zoom and ball distance. The base inference at `imgsz=1600` may put the ball at a scale that falls between the model's anchor grid spacings. A different inference resolution might align better.

### Key difference from hi-res retry
- Hi-res retry is a sequential fallback: try base → if zero, try 960 → done
- Multi-scale is a proactive sweep: try 640, 960, 1280 in parallel (logically) → first hit wins
- Multi-scale covers the possibility that the ball is detectable at a **lower** resolution (640) where the upscaling introduces less artifact, or at an **intermediate** resolution (960 or 1280) that happens to align with the model's anchor grid

### Implementation sketch

```python
# In recover_ball_rows(), for direct_seed windows only:

DIRECT_SEED_MULTI_SCALE = [640, 960, 1280]

if _proposal_window_kind_is_direct_seed(proposal_window_kind):
    candidate_rows = []
    for scale in DIRECT_SEED_MULTI_SCALE:
        candidate_rows = _predict_candidate_rows(
            imgsz=scale,
            inference_mode=f"multi_scale_{scale}",
        )
        if candidate_rows:
            break  # first scale to detect wins
else:
    # player_ranked and other windows: unchanged
    candidate_rows = _predict_candidate_rows(
        imgsz=prediction_settings["imgsz"],
        inference_mode="base",
    )
```

### Why this might succeed where single-scale fails
- YOLO's feature pyramid network (FPN) has specific "sweet spots" at certain input-to-feature ratios
- A ball that is 12px in a 111px crop:
  - at imgsz=640: the ball becomes ~69px in the inference tensor
  - at imgsz=960: the ball becomes ~104px
  - at imgsz=1280: the ball becomes ~138px
  - at imgsz=1600 (current): the ball becomes ~173px
- Each of these maps to a different level of the FPN, and the model's detection head may respond differently at each level
- The current single-scale approach gambles on one FPN level — multi-scale systematically tests three

### Cost
- ~3x inference time for direct-seed windows only
- Direct-seed windows are small crops — inference on a 111×111px image is very fast regardless of imgsz
- On the Blackwell GPU, this adds seconds to the total run, not minutes
- Player-ranked and all other recovery paths are untouched

### Diagnostics to add

```
proposalDirectSeedMultiScaleFrames
proposalDirectSeedMultiScaleDetectedFrames
proposalDirectSeedMultiScaleWinningScale (mode of winning scales)
```

### Risks and mitigations

| Risk | Mitigation |
|------|-----------|
| 3x inference cost on seed windows | Seed windows are tiny; fast even at 3x |
| Different scales produce conflicting detections | First-hit-wins policy avoids conflicts |
| Scale 640 produces lower-quality detections | Confidence threshold still applies |

---

## 8. Attack Vector C: Player-Ranked Spatial Bridge

### Thesis
Since `player_ranked` windows DO produce detections, use those detections as a spatial plausibility signal to credit direct-seed windows. Don't try to make the detector see the ball in tiny crops — instead, use the detector's success in larger crops to "claim" nearby seed locations.

### Why this is structurally different

The current pipeline treats `direct_seed` and `player_ranked` as independent detection channels:

```
direct_seed_tight → YOLO.predict() → 0 sports-ball detections
direct_seed_context → YOLO.predict() → 0 sports-ball detections  
player_ranked → YOLO.predict() → 9 sports-ball detections
```

Each window's detections are counted independently. Direct-seed gets zero credit even when a player-ranked detection physically overlaps the direct-seed region.

The bridge approach cross-references these channels:

```
For each frame where direct_seed found nothing:
  For each player_ranked detection in the same frame:
    If the detected ball's source box overlaps the direct_seed window:
      → Credit the direct_seed window with a "bridge" detection
      → Tag it as proposalInferenceMode="bridge_from_player_ranked"
```

### Why this doesn't violate the product contract

- **No new detector passes.** The ball detection is real — it was found by the model in the player-ranked crop.
- **No threshold changes.** The existing confidence threshold was already met.
- **No new classes.** Still COCO class 32 (sports ball).
- **The bridge is a post-processing attribution step**, not a detection step. It says: "this detection, which the model found in the larger crop, spatially corresponds to the seed location."
- The truth gates, clip length, frontend surface, and all other contracts remain unchanged.

### What this unlocks

If even a few bridge rows are credited, the `proposal_windows_075` profile's detection count rises above 9. This could make it competitive with `width_cap_075` (20 selected frames) during profile selection. If the proposal profile wins selection, the proposal geometry work from the previous 6 sprints starts paying off — the seed-centered, player-biased crops become the primary recovery path instead of the broad player-window crops.

### Implementation sketch

```python
# In _collapse_proposal_recovered_ball_candidates(), after per-frame best-row selection:

def _bridge_player_ranked_to_direct_seed(candidate_rows, seed_specs_by_frame):
    """
    For frames where direct-seed windows found nothing but player-ranked
    found a ball, check if the player-ranked ball detection overlaps any
    direct-seed window. If so, create a bridge row credited to the
    direct-seed window.
    """
    bridge_rows = []
    pr_rows_by_frame = {}
    ds_zero_frames = set()
    
    for row in candidate_rows:
        frame_id = int(row["Frame_ID"])
        kind = str(row.get("ProposalWindowKind", ""))
        if kind == "player_ranked":
            pr_rows_by_frame.setdefault(frame_id, []).append(row)
    
    # Identify frames where direct-seed was attempted but found nothing
    for frame_id, specs in seed_specs_by_frame.items():
        has_ds_spec = any(
            _proposal_window_kind_is_direct_seed(s.get("proposalWindowKind"))
            for s in specs
        )
        has_ds_detection = any(
            int(r["Frame_ID"]) == frame_id
            and _proposal_window_kind_is_direct_seed(r.get("ProposalWindowKind"))
            for r in candidate_rows
        )
        if has_ds_spec and not has_ds_detection:
            ds_zero_frames.add(frame_id)
    
    for frame_id in ds_zero_frames:
        pr_rows = pr_rows_by_frame.get(frame_id, [])
        ds_specs = [
            s for s in seed_specs_by_frame.get(frame_id, [])
            if _proposal_window_kind_is_direct_seed(s.get("proposalWindowKind"))
        ]
        for pr_row in pr_rows:
            ball_center = _row_source_box_center(pr_row)
            if ball_center is None:
                continue
            for ds_spec in ds_specs:
                if _point_in_crop_window(ball_center, ds_spec["window"]):
                    bridge_row = dict(pr_row)
                    bridge_row["ProposalWindowKind"] = ds_spec["proposalWindowKind"]
                    bridge_row["ProposalInferenceMode"] = "bridge_from_player_ranked"
                    bridge_rows.append(bridge_row)
                    break  # one bridge per PR detection per frame
    
    return bridge_rows
```

### Diagnostics to add

```
proposalBridgeFromPlayerRankedFrames
proposalBridgeFromPlayerRankedRows
proposalBridgeOverlapShare (% of PR detections that overlap a DS window)
```

### Risks and mitigations

| Risk | Mitigation |
|------|-----------|
| Player-ranked false positive propagated via bridge | Existing edge/anchor/support filtering catches most FPs |
| Bridge inflates direct-seed count artificially | Tagged explicitly as `bridge_from_player_ranked` — easy to filter in analysis |
| Confusing diagnostic interpretation | Separate bridge-specific counters prevent contamination of organic DS counts |
| Bridge rows may not improve profile selection | Only matters if enough bridge rows accumulate to shift profile ranking |

---

## 9. Attack Vector Comparison Matrix

| Dimension | A: Model Upgrade | B: Multi-Scale | C: Player-Ranked Bridge |
|-----------|-----------------|----------------|------------------------|
| **Addresses root cause?** | Directly (model capability) | Partially (scale mismatch) | Indirectly (attribution, not detection) |
| **Code changes needed** | None (model file swap) | Small (inference loop in `recover_ball_rows`) | Medium (new post-processing step) |
| **Risk of regressions** | Low — truth gates unchanged | Very low — only seed windows affected | Low — tagged explicitly |
| **Expected detection lift** | High (if v11s small-object attention works) | Medium (if ball is at a detectable scale) | Medium (credits existing detections) |
| **Inference cost change** | ~1.0–1.5x (model size increase) | ~3x on seed windows only (seconds) | Zero (no new inference) |
| **Time to first result** | ~30 min (download model, run proof) | ~2h (implement + one proof) | ~3h (implement + test + one proof) |
| **Combinable with others?** | Yes — B and C work on top of any model | Yes — complements A | Yes — complements A and B |
| **Diagnostic value if it fails** | Shows which model tier is needed | Shows scale is not the factor | Shows spatial overlap distribution |
| **Hard dependency** | Pod GPU for inference | None | Requires player-ranked to keep producing hits |

### Expected value ranking

1. **Attack A** — Highest expected value. Directly targets the root cause with zero code risk. If it works, the plateau breaks in one batch. If it fails, it narrows the problem to "even yolo11s can't detect balls in small COCO-pretrained crops" → clear signal that fine-tuning is needed.

2. **Attack B** — Medium expected value. Cheap additive layer. Most valuable when combined with A (different model + different scales = maximum coverage of the detection space).

3. **Attack C** — Medium expected value but highest conceptual value. Even if it doesn't break the numeric plateau, it reveals the spatial relationship between player-ranked hits and seed locations — which informs whether the seed positions are even correct.

---

## 10. Sequencing & Decision Framework

### Primary sequence

```
┌─────────────────────────────────────────────────┐
│ Other session: Hi-Res Retry (Batch A)           │
│   DIRECT_SEED_HI_RES_RETRY_IMGSZ = 960         │
│   Same model (yolov10n), same crop, higher res  │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
            Direct seed detections > 0?
                   /        \
                 Yes          No
                  │            │
                  ▼            ▼
         Promote &      ┌──────────────────────┐
         check gates    │ Attack A: Model swap  │
                        │ yolo11s.pt drop-in    │
                        │ Zero code changes     │
                        └─────────┬────────────┘
                                  │
                                  ▼
                       Direct seed detections > 0?
                              /        \
                            Yes          No
                             │            │
                             ▼            ▼
                      Promote &      Add Attack B
                      check gates    (multi-scale)
                                     on top of yolo11s
                                          │
                                          ▼
                                  Any scale hits?
                                     /       \
                                   Yes         No
                                    │           │
                                    ▼           ▼
                             Lock scale    Fine-tune model
                             & promote     on football ball
                                           crops (Attack A+)
```

### Decision rules

| Condition | Next action |
|-----------|-------------|
| Hi-res retry produces `DirectSeedHiResRetryDetectedFrames > 0` | Other session's approach wins. Run promotion. This plan becomes backup. |
| Hi-res retry produces 0 detections | Execute Attack A (yolo11s drop-in). |
| yolo11s produces direct-seed detections | Run full proof + promotion. If truth gates improve → done. |
| yolo11s still zero detections | Add Attack B (multi-scale) on top of yolo11s. |
| yolo11s + multi-scale still zero | The model needs domain-specific training → fine-tune on football ball crops. |
| Any model upgrade produces detections but truth gates don't improve | Run Attack C (bridge) to boost proposal profile selection. |

### Relationship to the other session's pre-committed fallback

The other session's plan states:

> If Batch A fails: stop the current proposal-geometry family as the main path. Move immediately to a seed-conditioned detector lane.

This analysis's Attack A *is* the "seed-conditioned detector lane" that the other session's plan describes as the fallback. This document provides the specific technical details for that lane.

---

## 11. Anti-Goals

These are explicit non-goals for the next batch, regardless of which attack vector is chosen:

- ❌ **Do not keep iterating on crop geometry.** Six sprints have proven this path is exhausted.
- ❌ **Do not lower confidence thresholds globally.** This pollutes `width_cap_075` and other broad profiles with false positives.
- ❌ **Do not add full-frame sweeps.** This is the opposite of the seed-focused strategy.
- ❌ **Do not change truth-gate thresholds.** The gates are working correctly — they correctly report that the pipeline's ball truth is inadequate.
- ❌ **Do not change clip length.** The 5-minute clip is the controlled variable.
- ❌ **Do not change `observedBall`, `inferredBall`, or `acceptedBall` semantics.**
- ❌ **Do not change the frontend or HTTP surface.**
- ❌ **Do not fine-tune on COCO-small-object subsets yet.** Try the model upgrade first.
- ❌ **Do not spend more than one batch before escalating.** If Attack A fails, move immediately to A + B, not to another geometry sprint.

---

## 12. Verification Plan

### For Attack A (model upgrade)

**Setup:**
```bash
# Download model to pod
wget -O /workspace/weights/yolo11s.pt \
  https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11s.pt

# Verify model loads and runs on GPU
source /workspace/fotball-venv/bin/activate
python3 -c "
from ultralytics import YOLO
import torch
model = YOLO('/workspace/weights/yolo11s.pt')
print('Model loaded:', type(model))
print('CUDA:', torch.cuda.is_available())
# Quick inference test on a dummy image
import numpy as np
dummy = np.zeros((640, 640, 3), dtype=np.uint8)
result = model.predict(dummy, imgsz=640, conf=0.1, classes=[32], verbose=False)
print('Inference OK')
"
```

**Proof run:**
```bash
python backend/scripts/run_local_app_path_proof.py \
  --video-path /workspace/fotball-analyst/videos/trimed-5min.mp4 \
  --model-path /workspace/weights/yolo11s.pt
```

**Key metrics to compare:**

| Metric | Baseline (v10n) | Target (v11s) |
|--------|----------------|---------------|
| `proposalDirectSeedDetectedFrames` | 0 | > 0 |
| `proposalDirectSeedTightDetectedFrames` | 0 | > 0 |
| `proposalPlayerRankedDetectedFrames` | 9 | ≥ 9 |
| `bestProposalSelectedFrames` | 9 | > 9 |
| `acceptedBallFrames` (after promotion) | 101 | ≥ 110 |
| `controlledPossessionFrames` (after promotion) | 98 | ≥ 105 |
| `ballTrackViable` (after promotion) | false | true |
| `ballTrackEdgeFrameShare` (after promotion) | 0.812 | < 0.6 |

### For Attack B (multi-scale)

Same proof loop, with multi-scale enabled. Additional diagnostics:

```
proposalDirectSeedMultiScaleFrames: (count of frames where multi-scale was used)
proposalDirectSeedMultiScaleDetectedFrames: (count of frames where any scale detected)
proposalDirectSeedScale640DetectedFrames: (detections at scale 640)
proposalDirectSeedScale960DetectedFrames: (detections at scale 960)
proposalDirectSeedScale1280DetectedFrames: (detections at scale 1280)
```

### For Attack C (bridge)

Same proof loop, with bridge enabled. Additional diagnostics:

```
proposalBridgeFromPlayerRankedFrames: (count of frames where bridge was applied)
proposalBridgeFromPlayerRankedRows: (total bridge rows created)
proposalBridgeOverlapShare: (fraction of PR detections that overlap DS windows)
```

### Product acceptance (same for all vectors)

At least one of:
- `acceptedBallFrames >= 110`
- `controlledPossessionFrames >= 105`
- `ballTrackViable == true`

### Hard stop rule

If **all three attack vectors fail** (model upgrade + multi-scale + bridge all produce zero improvement):
- The COCO-pretrained model family is exhausted for this crop distribution
- Next batch must be fine-tuning on football-specific ball crops
- Training data: extract positive crops from the 9 successful player-ranked detections + manual annotation of ball locations from the recovery video

---

## 13. Relationship to Existing Playbook

This analysis is consistent with the existing `video-analysis-enhancement-playbook.md` but adds urgency to one specific recommendation:

### Playbook says (Section 8, "What Not To Do Next"):
> "Do not rewrite the whole detector stack first"

### This analysis says:
The detector stack doesn't need a rewrite — it needs a **model swap**. The `run_guerilla.py` inference code stays identical. Only the `.pt` file changes. This is not a "detector stack rewrite." It's a configuration change.

### Playbook says (Section 3, "Core Design Shift"):
> "The next major improvement should not be 'another ball retry trick,' but a shift from ball-first truth to football-state truth."

### This analysis says:
The `acceptedMatchState v1` work (which has already landed) is the right medium-term direction. But state-first truth still needs *some* ball truth to bootstrap. Right now, 101 accepted ball frames with 0.812 edge share is not enough ball truth for the state layer to produce meaningful possession or event inference. Breaking the ball detection plateau is a prerequisite for the state layer to show its value.

### Playbook says (Section 9, Priority 5):
> "Upgrade player truth and off-ball value"

### This analysis says:
Player truth is already working well — 111 frames with reliable player detections, player-ranked windows consistently producing proposal hits. The weak link is ball truth, not player truth. Off-ball value is a valuable medium-term product direction, but it doesn't solve the current plateau.

---

*End of analysis.*
