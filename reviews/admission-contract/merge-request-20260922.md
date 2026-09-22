# Admission merge checkpoint — 2026-09-22

The repository owner explicitly requested merging the existing work into main and continuing the revised delivery TDD plan in a new branch/PR.

PR #195 was retargeted from the stacked delivery-retention branch to main. Its code head before this documentation-only commit was 225e4ac851298ade76c1a63d55790eb31bac795a. The earlier release artifact gate on that code head succeeded. A complete fresh CI result is still required; historical selected-test results are not a fresh full-suite run.

The separate PR #196 is still being reconciled with the complete T06 checkpoint. Do not infer that its old three-file head contains the tested T06 implementation.

Local environment observation in this session: the T06 checkpoint passes 177 Evidence Sets tests. Full collection is blocked by missing w3lib (5261 tests collected, six import errors); the frozen dependency installation could not complete because this container cannot resolve network hosts. These observations are limitations, not full acceptance.

No runtime, scorer, corpus, lockfile, workflow, or default-model changes are made by this commit.
