# Task 07 — narrow product scope and prove the core workflow

## Audit status

Complete for scope cleanup and claim hygiene. It did not prove product advantage: current decisive evidence is a negative signal and the new candidates were correctly rejected as too easy. Task 23 owns product proof.

## Problem

The repository contains Docs MCP, API Packs, patch constraints, hybrid retrieval, Qdrant management, USPTO ingestion, and 22 top-level CLI commands. This makes the product harder to explain and increases maintenance cost. Existing task-level pilots do not prove a broad improvement over repo-only agents.

## Goal

Make local documentation context the default product and keep other systems clearly advanced or maintenance-only.

## Required work

1. Define one primary user journey in README and installer output:
   `install → get_docs_context → follow prepare_docs when returned → answer with sources`.
2. Label MCP Packs and patch constraints as advanced surfaces.
3. Hide internal or compatibility CLI commands from beginner documentation without deleting them.
4. Record which unrelated subsystems are maintenance-only. Do not expand them during the roadmap.
5. Design three real-project tasks where critical information is distributed across project docs, lockfiles, and dependency docs and is not obvious from nearby code alone.

## Evidence rules

- Retrieval metrics prove retrieval only.
- Tool adoption proves discoverability only.
- Patch success requires public and hidden tests.
- Do not claim DocAtlas is better than repo-only until repeated policy-clean tasks support it.

## Acceptance criteria

- A new user can explain the core product after reading the first README screen.
- Beginner docs show one Docs workflow and no Packs details above the advanced section.
- At least three materialized real-project differentiation candidates pass fixture validation and fairness screening. Difficulty screening decides whether a candidate may set `differentiating=true`; candidates rejected as too easy must stay non-differentiating and cannot support product claims.
- Product claims map to a named benchmark metric.
