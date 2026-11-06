# V3 implementation contract — draft, source-feasibility blocked

Selection recipe `qwen3-contextual-addressed-section-closure-v3`;
structural recipe `explicit_addressed_section_closure_v3`; policy schema4.
Unchanged scoring subcontract — existing `context_evidence_scoring.CONTRACT`,
SHA256 `65dcde1445c86fe3d8245022e1b9db84f4c79cca4cd2ee868aa9d5234b863991`.
Scorer module/prompt/tokenization/BF16/SDPA/math/assets/runtime/input JSON не менялись.
Receipt wrapper отдельно связывает selection recipe/closure contract; это не
переименование исторического scorer. Old schema3 policy16fb92... не принимается v3.

## Structural semantics и syntax

Semantic seed — own body+ancestors, не subtree. Каждый фактически включённый
body, включая ancestors/definitions/children, обрабатывает links до fixpoint.
Heading anchor — unique section extent до следующего heading того же/меньшего
уровня; empty-heading target включает children. Local document path без fragment
— весь checked документ. Reference/footnote — whole definition-owner body и его
реальные links. Source order, full-body text и native provenance сохраняются.

Переиспользованы existing native parents/subtrees/slug anchors/quoted HTML
id/name, `_syntax` code/comment masking, `_edges` link/reference/footnote logic.
Нового production Markdown parser нет. V3-specific edge reporting включает:

- inline `[text](relative.md#anchor)`, `#anchor`, explicit relative `.md` или
  `.markdown` без fragment; existing balanced destination handling;
- full/collapsed/defined shortcut reference links, footnotes с whole owner;
- quoted lowercase HTML `href` и существующие quoted `id`/`name` anchors;
- normalization relative path + percentdecode, без raw source transformation;
- image reference/inline images и img/video/audio/source tags → unsupported asset
  gap, не документация/authorization; non-Markdown asset paths → unsupported;
- external scheme/netloc/query → target_not_in_checked_scope, без fetch;
- missing/ambiguous paths/anchors, scope mismatch → typed gaps;
- unresolved bracket-reference syntax/unquoted href → unsupported syntax gaps.

Existing masking удаляет inline-code markup, поэтому code-formatted reference
labels вроде ``[`interrupt`]`` не надёжно разрешимы. Empty masked label в v3
явно `unsupported_definition_label`; это source-visible limitation, не silent
successful resolution. Bare text URLs не считаются Markdown hyperlinks; parser
не претендует на все Markdown/HTML extensions. Неоднозначный/неподдержанный anchor
не выбирать эвристически. Footnotes/HTML assets/percent encoding вне нового
корпуса остаются code-review boundaries, не runtime proof.

Queue dedup по full native source identity+parent index, без depth/top-k/cap.
Path используется только для поиска кандидатов, неоднозначность не разрешается
первым match. Existing native scope/version/generation binding и whole-source live
qualification остаются обязательными до inference и для каждого delivery span.
Capability renewal code не изменён; new recipe входит в continuation fingerprint.

## Gaps и refusal

Для v3 EvidenceDocuments сохраняет aggregate `incoming_context_unresolved_count`
от всего checked graph; scoring JSON остаётся прежним. Это не delivered dependency
obligation. Closure начинает список obligations с пустого и добавляет gaps только
из реально включённых bodies. Historical v2 global-gap behavior не изменён.

В v3 любой delivered dependency gap → **body-free `dependency_incomplete` error,
hard_stop**, даже если model scan complete. Work receipt уже доступен observer,
без повторного count. Это не empty successful no-answer. Empty selected set не
получает gaps недопущенных документов. Scorer32k и delivery50k guards сохраняются;
нет truncation/full-subtree fallback ради50%. OFF не получает extra per-score
traces; retained gaps нужны для объяснения refusal, incoming diagnostics count-only.

## Independent oracle и новый policy fit

`prepare_annotations.py` — только offline annotation preparation, без DocAtlas
imports, scorer/closure calls или scoring/threshold simulation. Existing installed
markdown-it-py4.2.0 независимо извлекает headings/links/source-line maps. Raw offsets,
section extents, source-backed edges и definition owners сохраняются в review
inventory. Production parser не используется как expected value. Для acknowledged
unsupported code labels oracle также требует явный gap, не молча разрешённый edge.
Draft graph требует human/parent review; parser independence сама по себе не
доказывает correctness всех его annotations.

`source-extent-graph.json` — raw-source inventory; `reference_targets` перечисляют
полный addressed extent/definition owner; `reference_witnesses` содержат excerpt,
Unicode char spans, definition label и target. `draft-labels.json` содержит эти
inventory fields + роли по task. `fact-spans.json` фиксирует literal quotes/source
hash/spans. Expected required facts не вычисляются graph reachability.

Canonical tasks = прежние16 literal tasks + `holdout-tasks.json` и явные additions
`holdout-obligations-rev2.json`; затем independently derived ancestor obligations.
Актуальное число новых literal quotes — 39 (annotation-receipt.json).
Full required bodies проверяются наряду с quotes;
quotes не объявляются исчерпывающей семантикой всего upstream corpus.

Existing runner расширен opt-in `--v3-dataset`; `phase/packet_check/gates` и
accounting/readonly/resources переиспользованы. Independent closure BFS использует
только authored edge inventory, не production functions. Проверяются exact final
unit set/required facts/source hash/span/order, explicit gaps и nonempty body scan
inventory (empty headings не scorer units, но возможные required delivered rows).
Dependency-incomplete refusal не проходит как successful answer/no-answer.
Добавлен dependency gate к fit verdict: unresolved delivered graph не может
получить PASS через остальные metrics.

Future fit protocol (НЕ выполнялся): largest finite calibration breakpoint,
score>=tau, ties together, independent full closure preserves required obligations;
затем dependency/noanswer/hardnegative/50% gates. No fit against new holdout.
Policy schema4 связывает scoring SHA+new closure SHA+new manifest/calibration SHA.
Old numeric threshold/old calibration SHA не выдаются за v3 evidence.
После fit PASS — actual final replay в том же alive root/generation; прежние
validation8 доступны только command `seen`, separate parent seen authorization.
Новый holdout8 — command `validation`, separate parent authorization; автоматически
не вызывается. Для текущего blocked corpus эти commands запускать нельзя.

## Source/data scope и честные пределы

9 настоящих authored Markdown docs: OTel4allowed+1module-excluded, Embedded3allowed+
1module-excluded.12 downloaded raw files с licenses, pinned commits/originURLs/
SHA/byte counts в source-provenance.json. Relative upstream paths полностью
сохранены внутри каждого project root, bytes не нормализованы/обрезаны/переведены.
Collection конечный, не все upstream docs. Module restriction — experiment scope,
не реальное upstream access restriction. Native project docs индексируются как
unversioned; upstream commit provenance отдельно, cross-version mismatch holdout
не покрыт. Это upstream-authored, agent-selected/annotated, не blind external data.

Unreviewed bodies unlabelled; optional_support не выдуман. Новые in-scope true
hard negatives не заявлены: эта часть gate для нового holdout vacuous, scope-excluded
temptations настоящие. Старые16 true-hard-negative labels неизменны. Это ещё один
явный validation-design предел, не обещание exhaustive false-positive metric.
Полные prompts32k/VRAM feasibility не измерены — runtime запрещён. Raw docs
small enough для чтения, но это не доказательство полного model-input fit.

**Состояние:** код и artifacts подготовлены для review, а не для approval
inference. Raw graph даёт строгий source-feasibility blocker, описанный отдельно.
