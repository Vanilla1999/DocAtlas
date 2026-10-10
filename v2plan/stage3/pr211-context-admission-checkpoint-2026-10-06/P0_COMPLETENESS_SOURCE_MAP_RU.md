# P0: completeness/source-map classification

Прочитаны полностью `answer_completeness.py` (720 lines) и `source_map.py`
(934 lines). Оба mixed modules: **SPLIT**. Product/gold не менялись.

## D27 — completeness

`_STORY_MARKERS`, `_LAYER_TERMS`, `_RUSSIAN_REQUIREMENT_PATTERNS/ACTIONS`,
`_WEAK_STORY_SINGLETONS`, stopwords/generic relevance lists — NL semantics,
не технические enums. Story patterns включают закрытые заявки, отправку названия
в чат, первое обязательное поле; переносить их в новую alias/grammar table нельзя.
`_CODE_TERM_RE` смешивает literal identifier shape с перечнем Cubit/Service/etc.
Quoted/file spans и bounds сохраняются отдельно от inferred role/type.

Consumers внутри модуля: `_extract_requirements`/high-signal fallback →
`evaluate_project_answer_completeness` → matched/missing terms, coverage,
source-search action, legacy exact/partial и `edit_ready`.
`_item_text` включает path/title/heading/why_selected, а `_term_in_text` использует
substring для длинных terms. Такая coverage не является body-local proof.
Absent/explicit unmatched source items исключаются positive-proof filter:
сохранить этот guard, не превращать отсутствие в nonexistence proof.

`derive_project_answer_completeness` переопределяет status/coverage через canonical
`support_decision`, сохраняет `legacy_diagnostics`. Но next actions построены
legacy evaluation; при unsupported wrapper вычисляет `edit_ready` через
`has_safe_local_source_handoff(result['recommended_next_actions'])`.
Это реальный мост legacy semantics→handoff, не только diagnostic serialization.
Удаление словарей не должно безусловно разрешать edit или терять partial context.

Source callers: project-context part01 `:230` extraction fallback, `:670`
relevance fallback, `:738` canonical derive; shared `:391` relevance gate.
Direct `evaluate` не имеет найденных production callers вне wrapper в данном scan;
он остаётся SDK-callable, но не объявлен default verdict authority.

## D31 — source map

`_STATUS_TOKEN_RE` → status-like extraction/rendering;
`_QUERY_STOPWORDS` → `_query_terms` → selection/evidence terms;
`_source_evidence_terms` prioritizes Gate/Service/Repository/etc suffixes;
`_question_requests_generated_artifacts` открывает generated files из NL cues
при `include_generated=None`. Explicit `include_generated` bypasses inference.
Это semantic/default scope policy, не blanket file-format exception.

Technical retain candidates: extension→language registry, Python AST/imports,
source grammar keywords, literal string/code shapes, offsets/lines, request-local
immutable captures, redaction. Preserve `SourceBoundary`/bounded traversal.
Generic fuzzy/token matching не словарь, но high match confidence не proof.
Exact-path match выдаёт first non-empty line как discovery witness, не доказательство
содержательного ответа на вопрос. Absent item явно не доказывает nonexistence.
First-selected-item budget exceptions (`if selected and ...`) — recorded behavior,
не подтверждение strict budget compliance; P0 не меняет budget contract.

Source callers: patch constraints part01 `:176–177`, project context part01
`:261/:286`, shared `:133`, code context `:54`, code graph part01 `:90`,
project state `:265` (fallback question `architecture`). Эти read/patch/graph
consumers остаются в migration scope; static named edges не full runtime proof.
