# P0: structural и mixed classifications

Статус: **P0 ACTIVE**. Production/test/gold bytes не менялись.

Расширена поимённая классификация в `p0_structural_classification.py`.
Source hashes проверяются прежним runner перед применением решений.
Technical retain — предложение для P1, не утверждённое исключение.

## Основания

- Evidence/retrieval DTOs: serialization и explicit enum/bounds validation;
  semantics producers, authority и completeness certification отдельно.
- HTML/context rendering: markup grammar/entity decoding/XML escaping и style
  dispatch; никакой тематической query→answer таблицы.
- Target security/storage locks: explicit URL/allowlists/IP checks, OS lock/lease
  identities; эти guards нельзя удалить вместе со смысловыми recognizers.
- Source identity/subject binding: supplied identity serialization, raw hash,
  exact window и structural owner verification; не title-based proof.
- Query script runs: verbatim bounded script extraction, не перевод и не proof.
- Context quality: explicit covered/missing mandatory IDs и unresolved residue;
  при миграции producers нельзя превратить status enum в blanket proof exception.
- Public input normalization: optional lookup array validation, duplicates/caps,
  serialized token estimate; не обязательная cross-language decomposition.
- Support policy/staleness: explicit support-surface registry и timestamp/source
  policies; внешние policy contents не покрыты этим Python-module решением.
- Error contract: reason enums/serialization отдельно от caller workflow hints.

Mixed modules классифицированы как **SPLIT**, с конкретными механизмами:
`normative_language` (D25), `context_request_preferences` (D35),
`evidence_semantic_density` (D36), `admission_local_binding` (D21),
`context_hint_policy` (D19), `lifecycle_policy` (D18),
`context_query_probes` (D26), `project_answer_outline` (D13).
Их NL cues и keyword-derived coverage нельзя сохранить под technical exemption;
raw source/spans/bounds/partial attribution guards сохраняются отдельно.

Structural AST rules ограничены `Literal` enum declarations и прямым same-name
field copying (включая list/tuple container conversion). Это классификация
конкретной операции, не approval для значений/producer. Проверки отклоняют
synonym dictionaries, renamed fields, topic-to-call dispatch, keyword branches
и literal permission synthesis. **12 controls passed**;
`archives/p0-structural-checks.json`. Product tests не заменялись.

## Текущие числа

- Raw candidates: 9874; classified: **1856**, unresolved: **8018**.
- Review units: 2624; node-complete: **438**, existing owner decision: **102**,
  требуют review: **2084**.
- Grouping сохраняет все IDs; pinned hashes всех 383 Python-файлов проверены.

Это прогресс классификации, **не выполнение запроса «всё классифицировать»**.
Оставшиеся units не получают blanket SPLIT/technical отметку ради нулевого
счётчика. Consumer closure также не следует из AST classification.
