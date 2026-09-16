# Product Context

## Why This Project Exists

Professional football analytics tooling is expensive, operationally heavy, and often inaccessible to grassroots teams. This project exists to make useful football analysis possible with commodity hardware, local processing, and transparent artifacts instead of black-box vendor platforms.

## The Problem It Solves

Grassroots teams usually have video but not structured data. Coaches can watch clips, but they cannot easily answer questions like:

- where did our build-up break down?
- how stable was our possession structure?
- when did the ball tracking become untrustworthy?
- what moments should be reviewed or exported?

This project turns raw video into:

- structured frames and events
- truth layers and proof summaries
- review and annotation surfaces
- tactical exports and summary artifacts

## Primary Users

- solo coaches and analysts
- small academies
- teams running single-camera match capture
- engineers iterating on proof quality and robustness lanes

## How It Should Feel

The system should feel:

- local-first
- inspectable
- recoverable when quality drops
- useful for both product users and engineering iteration

Users should be able to move from raw video to a match record, review surface, and proof artifacts without needing hidden operator knowledge.

## UX Goals

- uploads and processing should be understandable, with job progress visible
- match review should expose useful layers rather than raw pipeline noise
- uncertainty should be surfaced as trust crops or proof artifacts, not silently hidden
- exports and summaries should be easy to generate from saved state
- when remote compute is used, it should behave like an extension of the local workflow rather than a separate product

## Current Product Reality

The product already supports:

- local upload and processing
- backend artifact persistence
- frontend review surfaces
- AI-assisted reports and tactical summaries
- RunPod-backed proof execution
- benchmark suites over saved matches

The current weakness is not basic plumbing. It is reliability across source clips, especially on `trimed-5min.mp4`, where the ball track remains edge-heavy and non-viable.
