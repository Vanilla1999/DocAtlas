# Structural v2: дизайн на review, production пока v1

Обновление этапа3: конкретное предложение для открытого Qwen scorer находится в
`../step10-open-scorer/DESIGN_CHECKPOINT_RU.md` и `recipe-draft.json`: anchors дают
контекст target classifier, но больше не автоматический target subtree. Ниже
сохранён первоначальный вариант для истории design review; его консервативный
anchor-subtree пункт НЕ является новым утверждённым runtime контрактом. Новый
вариант также ждёт parent review; source-read full-section semantics сохраняются.

Это изменение policy, не bugfix существующего subtree contract. V1 и frozen
artifacts сохраняются. Предлагаемое имя: minimal-structure-evidence-v2.

## Typed obligations

- evidence_sentence: classifier допускает конкретное предложение в проверенном
  полном документе; оно отображается в собственный авторский body-раздел.
- own_body: доставить весь body с заголовком, неделимыми списками/таблицами/кодом,
  его ancestor introductions и preamble. Не расширять потомков этого seed.
- explicit_section: выполнить явный запрос полного раздела с дочерними секциями.
  Для публичного source read известная адресованная секция — структурная команда,
  а не проход intro через relevance. Естественно-языковой full-section запрос
  требует отдельного query-intent/target binding, который пока не реализован.
  Не распознавать его списком слов и не создавать endpoint только для benchmark.
  До утверждения механизма C-L2/V-C2 остаются обязательными открытыми gates.
- reference_definition/footnote: включить цельный definition owner и его контекст.
- anchor_target: текущий консервативный вариант включает target subtree с
  source checks. Navigation amplification НЕ решён; это измеряемый blocker,
  а не основание ограничить глубину/число ссылок.

Очередь фиксированной точки хранит тип обязательства. Повторное добавление
ancestor own_body не превращает его в subtree seed. Visited содержит полную
source identity, section и obligation type. Циклы завершаются без квоты глубины.
Source-validity и terminal recheck остаются независимыми от semantic решения.

## Classifier input review до реализации

Authentic EXIT оценивает исходное предложение, original question и полный
содержащий документ. Не склеивать разные documents в Full context. Prompt,
special tokens, точные Yes/No ids, dtype и база+adapter закрепляются manifest.
Sentence offsets должны указывать в original bytes; списки/код/таблицы не
превращать в перефразированный текст. Стратегия сегментации Markdown (особенно
code/table) ещё не утверждена. Для этих units нельзя молча подменить sentence
вход обученного classifier целым paragraph и назвать это воспроизведением EXIT.
Overflow полного prompt — явный incomplete, без truncation или скрытого fallback.
Multilingual и длиннодокументная recipe требуют отдельных доказательств.

## Endpoints и consumers для следующего diff

1. get_docs_context: docs/interfaces/mcp/context_tools.py и docs_context_routing.py;
   focused source_path задаёт scope, но не обязательно запрос всего документа.
   Не смешивать focused semantic query с explicit full-section read.
2. joint_context_selection.py: select_context → select_minimal_context; сохранять
   opt-in/default off и source-valid full acquisition.
3. minimal_context_selection.py: policy schema/structural recipe, typed seeds,
   settings в continuation_fingerprint, observer receipts и terminal recheck.
4. minimal_context_structure.py: build_units, source offsets, close_selection,
   _hydrate/recheck_structural_row; v1 dispatch сохраняется без переинтерпретации.
5. source_continuation.py / _source_continuation_core.py и MCP read_docs_source /
   resources: публичный чтительный контракт целого раздела и cursor exhaustion;
   policy change не должна удалить детей из явного source read.
6. model_visible_projection.py, standalone_text_view.py, context_assembly.py:
   дословные spans, refs и отсутствие выдуманного непрерывного диапазона.
7. Все source URI bindings, scope/version/hash rechecks и atomic registration
   сохраняются. Stale old-policy continuation нельзя принимать под новой recipe.
8. Existing public probes и новый project-level evaluator: фиксировать direct,
   ancestor, definition, anchor subtree и explicit section отдельно.

## Проверки после review

Один существующий source-read/continuation integration сохраняет полные дочерние
блоки и stale/replay semantics. Новый multilingual gate проверяет own-body seed
без автоматического sibling admission; C-L2/V-C2 — полноту явного раздела.
Точные facts/условия и source bytes являются verdict, diagnostic причина лишь
объясняет его. На adversarial navigation link допускается FAIL до обоснованного
решения; нельзя назвать большое closure достаточным semantic quality.
