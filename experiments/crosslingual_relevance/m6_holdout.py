"""Replays inspected M1.5 tasks with a real scorer or EXPLICIT oracle plumbing.

The historical module name is retained for compatibility. These tasks are not
an unseen-domain holdout. Default scoring is real; --oracle-plumbing is opt-in
and its output cannot be promoted to model-quality evidence. Old artifacts and
protocol locks are never overwritten.
"""
from __future__ import annotations
import argparse
from contextlib import nullcontext
import json
from pathlib import Path
import tempfile
import uuid
from typing import Any

from eval.evidence_quality_v2.observer import observe_call
from eval.evidence_quality_v2.runtime import write_project, isolated_service, index_project
from eval.evidence_quality_v2.run import documents_for, load_protocol, audit_payload
from docmancer.docs.application.model_visible_projection import docs_context_budget_tokens
from .context_rescue import installed, BoundedScorer, M2B_THRESHOLD
from .mpnet_scorer import mpnet_scorer, model_identity, _get_model
from .m5_real_scorer import _build_vector_service, _index_all
from .evaluation_v2 import assess_packet, canonical_row, corpus_documents, save_new_report

# Holdout tasks from M1.5 frozen manifest
HOLDOUT_TASKS = [
    {
        "id": "m15-hold-01", "project": "httpx", "formulation": "mixed",
        "question": "Как отключить all timeouts для HTTPX Client: какой аргумент передать?",
        "gold_path": "docs/advanced/timeouts.md",
        "gold_lines": [(32, 39), (19, 28)],
        "gold_phrases": ["timeout=None", "Disable all timeouts by default"],
        "fact_id": "httpx-disable-timeouts",
    },
    {
        "id": "m15-hold-02", "project": "ruff", "formulation": "EN",
        "question": "What happens to explicit-preview-rules setting when preview mode is not enabled?",
        "gold_path": "docs/preview.md",
        "gold_lines": [(182, 182), (159, 161)],
        "gold_phrases": ["this setting has no effect", "preview mode is not enabled"],
        "fact_id": "ruff-explicit-preview-no-effect",
    },
    {
        "id": "m15-hold-03", "project": "starlette", "formulation": "RU",
        "question": "Как использовать TestClient, чтобы lifespan выполнился в тестах?",
        "gold_path": "docs/lifespan.md",
        "gold_lines": [(78, 92)],
        "gold_phrases": ["TestClient", "context manager", "lifespan is called"],
        "fact_id": "starlette-testclient-context-manager",
    },
    {
        "id": "m15-hold-04", "project": "pydantic", "formulation": "mixed",
        "question": "Как AliasGenerator помогает use different naming conventions при loading and saving?",
        "gold_path": "docs/concepts/alias.md",
        "gold_lines": [(136, 140)],
        "gold_phrases": ["AliasGenerator", "different alias generators", "loading and saving"],
        "fact_id": "pydantic-aliasgenerator-purpose",
    },
]


def _gold_scorer_factory(task):
    """Oracle is only a plumbing control, never a relevance-model result."""
    from .evaluation_v2 import required_claims
    claims=required_claims(task)
    def scorer(question, text):
        return .9 if any(all(c in text for c in alt["clauses"])
                         for claim in claims for alt in claim["alternatives"]) else .1
    scorer.identity=lambda:{"kind":"oracle_plumbing","verified":False}
    return scorer


def _is_gold_source(source, task):
    outcome=assess_packet({"sources":[source]},task)
    return outcome["all_required_facts"] and not outcome["canonical_errors"]


def _is_gold_in_candidates(trace, task):
    rows=[s for e in trace.get("stages",{}).get("retrieved_candidates",[])
          for s in e.get("sources",[]) if isinstance(s,dict)]
    return assess_packet({"sources":rows},task)["all_required_facts"]


def _run_condition(service, root: str, task: dict, condition: str, *, oracle_plumbing: bool=False):
    request={"question":task["question"],"project_path":root,"scope":"all"}
    use_rescue=condition in {"dense_rescue","lexical_rescue"}
    scorer=_gold_scorer_factory(task) if oracle_plumbing else mpnet_scorer
    bounded=BoundedScorer(scorer,capture_text=True)
    context=installed(bounded,question=task["question"]) if use_rescue else nullcontext()
    with context:
        payload,trace=observe_call(service,request)
    # Handler failures are not malformed model-visible projections.
    errors=(audit_payload(payload,trace.get("snapshot",{}),Path(root))
            if payload.get('status') != 'failed' else ['handler failed: '+str(payload.get('error',{}).get('exception_type'))])
    assessment=assess_packet(payload,task,audit_errors=errors)
    candidates=[s for e in trace.get("stages",{}).get("retrieved_candidates",[])
                for s in e.get("sources",[]) if isinstance(s,dict)]
    docs=corpus_documents(task["project"])
    candidate_checks=[canonical_row(s,docs) for s in candidates]
    return {"task_id":task["id"],"condition":condition,"formulation":task["formulation"],
            "evaluation_kind":"oracle_plumbing" if oracle_plumbing else "real_model_replay",
            "gold_oracle_used":oracle_plumbing and use_rescue,
            "independent_holdout":False,
            "model_executed":use_rescue and not oracle_plumbing and bounded.summary["evaluations"]>0,
            "model_identity":bounded.identity(),
            "document_found":any(s["status"]=="verified" for s in candidate_checks),
            "all_required_in_candidates":_is_gold_in_candidates(trace,task),
            "gold_in_packet":assessment["all_required_facts"],
            "assessment":assessment,"budget_tokens":docs_context_budget_tokens(payload),
            "admission_errors":{"false_admit":None,"false_reject":None,
                                "reason":"requires_exhaustive_candidate_relevance_labels"},
            "source_policy_errors":errors,
            "payload":payload,"trace":trace,
            "scorer_events":bounded.events,"scorer_summary":bounded.summary}


def valid_for_model_quality(row: dict) -> bool:
    return (row.get("evaluation_kind")=="real_model_replay"
            and row.get("gold_oracle_used") is False
            and row.get("model_executed") is True
            and row.get("model_identity",{}).get("verified") is True
            and not row.get("scorer_summary",{}).get("degraded")
            and row.get("assessment",{}).get("source_policy_status")=="PASS")


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oracle-plumbing',action='store_true')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--max-sections-per-source',type=int,choices=(2,20),default=20)
    args=parser.parse_args(argv)
    root=Path(tempfile.mkdtemp(prefix='m6-reviewed-'))
    manifest=load_protocol()[2]
    roots={}
    for project in {t['project'] for t in HOLDOUT_TASKS}:
        path=root/'projects'/project
        write_project(path,documents_for(project,manifest))
        roots[project]=path
    # Dense retrieval is real even for the explicit oracle scorer condition.
    # Pin it to the same checked artifact as the MPNet scorer.
    from .pinned_embedding_session import pinned_embeddings
    results=[]
    with pinned_embeddings():
        vservice,vconfig,patcher=_build_vector_service(root/'dense',max_sections_per_source=args.max_sections_per_source)
        vconfig.retrieval.max_sections_per_source=args.max_sections_per_source
        try:
            _index_all(vservice,{k:str(v) for k,v in roots.items()})
            # isolated_service changes process-global environment; keep the
            # vector service on its own environment before entering that context.
            for rescue in (False,True):
                for task in HOLDOUT_TASKS:
                    results.append(_run_condition(vservice,str(roots[task['project']]),task,
                        'dense'+('_rescue' if rescue else '_baseline'),
                        oracle_plumbing=args.oracle_plumbing))
            with isolated_service(root/'lexical') as (lservice,lconfig):
                lconfig.retrieval.max_sections_per_source=args.max_sections_per_source
                for path in roots.values(): index_project(lservice,lconfig,path)
                for rescue in (False,True):
                    for task in HOLDOUT_TASKS:
                        results.append(_run_condition(lservice,str(roots[task['project']]),task,
                            'lexical'+('_rescue' if rescue else '_baseline'),
                            oracle_plumbing=args.oracle_plumbing))
        finally:
            patcher.stop()
    output={'schema_version':2,'evaluation_kind':'oracle_plumbing' if args.oracle_plumbing else 'real_model_replay',
            'independent_holdout':False,'frozen_threshold':M2B_THRESHOLD,
            'max_sections_per_source':args.max_sections_per_source,
            'rows':results,'summary':{'all_required_first_packets':sum(r['gold_in_packet'] for r in results),
                                    'total':len(results),
                                    'model_quality_eligible_rows':sum(valid_for_model_quality(r) for r in results)}}
    target=args.output or Path(__file__).parent/'review_runs'/f'm6-{output["evaluation_kind"]}-{uuid.uuid4().hex}.json'
    save_new_report(target,json.loads(json.dumps(output,default=str)))
    print(target)


if __name__=='__main__':
    main()
