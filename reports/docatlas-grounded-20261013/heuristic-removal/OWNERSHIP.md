# Ownership — 2026-10-13

Base 91dd2b4e; isolated branch experiment/heuristic-removal-20261013.
Source reports: /home/viadmin/StudioProjects/hermes/docmancer/reports/docatlas-grounded-20261013/.

- A: core/_sqlite_store_part03.py, retrieval/**; A_ACQUISITION.md.
- B: docs/domain/evidence_qualification.py, ordinary_body_context.py, literal_context_admission.py, query_reference_binding.py; B_ADMISSION_CONTRACT.md.
- C: docs/application/_project_docs_service_part03.py, experimental_candidate_selection.py, experimental_selection_modes.py, experimental_prepared_parent_assembler.py, experimental_context_finalization.py, joint_context*.py, _docs_context_projection_core.py (extended after B handoff, before edits); C_SELECTION_ASSEMBLY.md.
- D: eval/heuristic_removal_holdout/**; D_RESEARCH_AND_EVALUATION.md, METHOD_CONFORMANCE.md. Holdout oracle hidden from implementers until code freeze.
- E: tests integration scenario(s), eval/heuristic_removal/**; E_EXECUTION_PROTOCOL.md. No workloads: coordinator only.
- Coordinator: shared interfaces outside ownership, docs/application/docs_context_projection.py, _project_context_service_part01.py, _project_context_service_shared.py (C integration blockers, assigned before edits), inventory/protocol/manifest/checkpoint/results, sequential execution.
- F: fresh review after results, no product edits/reruns.

Workers do not delegate or run product/tests/benchmarks. No overlapping edits; request ownership extension before changing other files. Use patch for edits. No unit. No commit/push/promotion. Default remains unchanged until explicit decision; candidate removal must be real on isolated experiment path, not semantic rescue.
