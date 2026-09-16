# Memory Bank

This folder is the project memory bank for `fotball-analyst`.

It is meant to be the fastest way to rebuild context when returning to the repo after a break. The six core files are the primary entrypoints:

1. `projectbrief.md`
2. `productContext.md`
3. `activeContext.md`
4. `systemPatterns.md`
5. `techContext.md`
6. `progress.md`

Supporting notes live in subfolders when a topic needs more structure:

- `currentRoadmap.md` for the currently valid cross-project roadmap
- `architecture/` for repo and system layout
- `features/` for lane-specific or feature-specific context
- `operations/` for repeatable workflows such as RunPod and verification

Recommended reading order:

1. `projectbrief.md`
2. `productContext.md`
3. `activeContext.md`
4. whichever supporting doc matches the task
5. `systemPatterns.md`
6. `techContext.md`
7. `progress.md`

Update rules:

- update `activeContext.md` whenever the active engineering lane changes
- update `progress.md` whenever a milestone is finished or falsified
- update `systemPatterns.md` when architecture or major workflows change
- update supporting docs when a lane or operational workflow changes materially
