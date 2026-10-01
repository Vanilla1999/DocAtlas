# Task 05 — build a credible Context7 parity evaluation

## Audit status

Partial scaffolding only. The dataset and scorer exist, but no runner captures the DocAtlas side and the current relevance/coverage protocol can produce misleading results. Task 18 supersedes the unfinished acceptance work.

## Problem

Current saved snapshots have only two or three queries per library. Perfect Hit@1 on that sample is a regression signal, not proof of parity.

## Goal

Create a reproducible evaluation that compares DocAtlas and Context7 on the same libraries, versions, questions, and expected evidence.

## Dataset

Start with at least:

- 10 Python libraries;
- 10 JavaScript/TypeScript libraries;
- 5 Dart/Flutter libraries;
- 5 version-sensitive questions per library;
- a mix of API usage, migration, configuration, and code-example questions.

Every item must define the requested version, allowed corpus, expected source or section, and whether a usable code snippet is required.

## Metrics

- first-tool accuracy;
- Hit@1, Hit@3, MRR;
- version mismatch rate;
- snippet presence and basic syntax validation;
- cold and warm latency;
- network fetch count;
- unnecessary lifecycle-call rate;
- source contamination rate.

## Rules

- Use identical questions and version constraints for both products.
- Store raw traces separately from summarized committed results.
- Do not describe a win when the sample or source rules differ.
- Keep task-level patch success as a separate benchmark.

## Acceptance criteria

- At least 150 committed evaluation items.
- A single documented command reproduces the DocAtlas side.
- Results include confidence intervals or per-item output, not only averages.
- The report clearly lists wins, losses, and unsupported cases.
