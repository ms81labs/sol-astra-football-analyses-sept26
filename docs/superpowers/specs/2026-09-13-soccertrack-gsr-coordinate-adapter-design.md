# SoccerTrack GSR Coordinate Adapter Design

## Goal

Stream bounded player-state windows from the retained SoccerTrack v2 GSR files into the existing external match bundle while preserving source coordinates, identity, half, and ground-truth provenance.

## Correct source contract

The retained GSR files, and the current upstream format warning, contradict the older cached flat-record description. The shipped files are SoccerNet-COCO objects with `info`, `images`, `annotations`, and `categories`. Entity annotations have string `image_id` values made from a sequence prefix plus a one-indexed six-digit frame number. `role`, `jersey`, `team`, and `player_id` live under `attributes`; metric position lives at `bbox_pitch.x_bottom_middle` and `bbox_pitch.y_bottom_middle`.

The adapter follows those shipped bytes. It does not use the stale flat-schema mapping or load either multi-gigabyte file with `json.load`.

## Bounded streaming

The existing SoccerTrack adapter gains one standard-library JSON-array iterator. It scans fixed-size text chunks until the top-level `annotations` array, decodes one JSON value at a time with `json.JSONDecoder.raw_decode`, and discards consumed text. A single annotation may not exceed 8 MiB; malformed or unexpectedly large records fail closed.

The first evaluation fixture reads a declared 20-frame window from each half. Parsing stops after the first annotation beyond the requested window because the shipped annotations are frame ordered. Tests exercise chunk boundaries and prove the parser stops without consuming trailing records.

## Frame and entity mapping

For each half:

- `frameIndex` is the one-indexed six-digit suffix of `image_id`, minus one;
- `timestampSecondsInHalf` is `frameIndex / info.frame_rate`;
- `trackId` remains the per-half integer track identifier;
- `playerId` remains an opaque string when present and is the preferred cross-half identity;
- `role`, numeric-or-null `jerseyNumber`, and `teamSide` preserve source values;
- `pitchPositionMeters` preserves centre-origin `(x, y)` without clipping;
- `pitchPositionNormalized.x = (x + 52.5) / 105 * 100`;
- `pitchPositionNormalized.y = (34 - y) / 68 * 100`, converting source-positive-up to the application's top-to-bottom display axis without clipping.

Rows without a usable metric position are counted and omitted from the entity list, not silently converted to zero. The frame remains present when other entity annotations establish it.

## External bundle

The existing bridge uses `gsrFrames` instead of the MOT metadata sample. Each exported frame has a unique integer `frameId` derived from half and frame index, half-relative time, and a populated `players` list carrying both metric and normalized positions plus identity/team/role fields.

The bundle marks these frames as `soccertrack_gsr_ground_truth`, `referenceOnly=true`, and `referenceLabelsUsedForInference=false`. Left/right is not converted to `my_team`/`enemy`, because source side flips by half and no analyst team selection exists. The reference bundle is evaluation input; it is never written into normal match storage or fed to video inference.

## Evidence and documentation

The adapter audit records requested/read frame counts, entity counts, omitted-position counts, source paths, half numbers, frame rates, and the shipped schema name. The readiness report is corrected to name the shipped-schema mismatch. Current status continues to classify this as dataset adaptation, not actual inference or labeled accuracy.

## Verification

Red-green tests cover chunked parsing, prefixed frame IDs, nested fields, coordinate conversion, null positions, half separation, bridge population, and reference-only provenance. A bounded real-data execution against both retained halves verifies that the code reads actual player coordinates without loading the full files. No video download, training, model promotion, provider call, or runtime-default mutation occurs.
