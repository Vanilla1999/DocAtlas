# Project answer quality protocol v4

Immutable provider-free hermetic protocol for the QuestionPlan safety boundary. It proves that unresolved subjects and operations fail closed, compound questions require every mandatory facet, paraphrases preserve intent, exact proof outranks generic project text, and selected eval documentation can be used without widening the whole `eval/` tree.

This protocol intentionally freezes the answer projection before the retrieval-only fallback. It is a parser, proof, selection, and citation microbenchmark over synthetic repositories; it does not prove the current-repository final routing behavior. Run `python scripts/run_project_docs_self_host_gate.py` for the separate live production-path, context-first gate.


Contamination protection means that forbidden distractor fragments or paths must never become selected or model-visible evidence for a supported answer.

Validate the frozen protocol lock with:

```bash
python eval/project_answer_quality_v4_protocol.py --validate-protocol
```

Run the hermetic provider-free v4 protocol and write its deterministic report with:

```bash
python eval/project_answer_quality_v4_protocol.py --output /tmp/project-answer-quality-v4-hermetic.json
```

Run the unpatched current-repository context-first gate separately:

```bash
python scripts/run_project_docs_self_host_gate.py --output /tmp/project-answer-quality-v4-live.json
```

The live report records Top-3 relevance, MRR, distractor and historical-source rates, query coverage, citation hashes, expected fact checks, and false abstentions.
