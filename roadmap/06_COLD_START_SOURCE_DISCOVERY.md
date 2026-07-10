# Task 06 — reduce cold-start cost for public dependency docs

## Problem

Context7 can answer popular public-library questions with almost no setup. DocAtlas may need source resolution, crawling, extraction, and indexing before the first useful answer.

## Goal

Make the first exact-version answer fast for the priority ecosystems without requiring a hosted query backend.

## Required work

1. Define a versioned source-manifest schema containing official documentation roots, version URL rules, allowed domains, preferred `llms.txt`/sitemap seeds, and extraction format.
2. Ship a small curated manifest set for the libraries used by the parity evaluation.
3. Cache fetched snapshots by canonical source identity and content hash.
4. Prefer bounded official sources; never guess arbitrary URLs silently.
5. Return one exact `prepare_docs` action when network acquisition is required.

## Priority gaps

- Poetry lock and PDM lock support;
- Bun lock/workspace support;
- versioned ReadTheDocs and framework documentation;
- duplicate-version handling in lockfiles.

## Non-goals

- No large hosted library catalog in this task.
- No enterprise connectors.
- No background network access without confirmation.

## Acceptance criteria

- Typical curated library reaches first useful context in under 10 seconds on a normal connection.
- Warm queries use the local snapshot and perform no network calls.
- Exact available lockfile versions never silently fall back to latest docs.
