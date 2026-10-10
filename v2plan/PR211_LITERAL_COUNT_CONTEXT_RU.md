# PR #211: literal count context без вывода количества

Статус: production + existing recovery controls; новый runtime результат **pending**.
Base: `80c8fbbb3e8c379467a9075f93f7165d080f8432`.

## Подтверждённая база

[Actual recovery job](https://github.com/Vanilla1999/DocAtlas/actions/runs/38006157209/job/114075319327)
на опубликованном base: **12 passed, 0 failure, 0 error**, затем **18 intended guard kills**.
`closed_literal_context` прошёл 9 real positive reads, 20 negative reads и 29 сравнений состояния.
Это существующая здоровая база; результат нового count route из неё не выводится.

## Узкий контракт

Допускается только полностью потреблённый синтаксис:

```text
How many <literal word phrase> does <literal identifier> allow?
```

Identifier берётся из настоящего `QueryMention`: bare, unresolved, `isidentifier()`.
Phrase — исходная непустая последовательность word tokens, разделённых пробелами или tab;
её регистр, написание и разделители не нормализуются. Внешний frame допускает иной регистр
и внешние whitespace, но второй `does`, второй subject и хвост после `allow?` не принимаются.
Это синтаксическая граница одной формы, без словаря предметной области, перефразирования или alias lookup.

Сначала выполняются все прежние проверки полного catalog/member binding, scope, project,
generation, raw-document SHA, current lifecycle и окна. Новый путь возможен только после
канонического `insufficient_visible_match`; другое отклонение не превращается в fallback.

Затем требуется одна сохранённая body paragraph unit:

- текущий `_relation_units` должен сохранить весь абзац без структурного преобразования;
- identifier и **цельная** phrase должны буквально присутствовать в исходном абзаце;
- их raw spans не перекрываются;
- удаление обеих literal strings оставляет содержательный текст;
- headings, link-only text, чистая label, разные абзацы и перенос внутри phrase не дают pair witness.

Whitespace-normalized представление используется только для проверки структурной границы.
Все query/body координаты вычисляются из исходных строк и возвращаются как диагностические spans.
Обычный identifier witness сохраняет прежние поля, count route добавляет `kind=literal_count_context`
и вложенный `literal_phrase`; новой reference role из этого не создаётся.

`query-original` остаётся missing/unverified, `coverage_credit=False`;
source context не даёт `answer_supported`, `answer_available`, `edit_ready`,
не доказывает число, разрешение или отношение между сущностями.
Пороги qualification и ranking, acquisition, query plan, source ownership и projection guards не меняются.

## Независимые проверки в существующем case

Обычные test functions и 12 recovery case names не добавлены и не удалены.
В конец существующего `closed_literal_context` добавлен отдельный non-P14 fixture:

```text
λ ledger. LeaseRetryWindow retains four renewal attempts in its ledger.
```

Слово `allow` в документе отсутствует. Два настоящих public reads проверяют обычную форму
и frame с внешними whitespace/верхним регистром. Независимый `str.index` oracle требует точных
raw query/body spans identifier и phrase; символ λ перед identifier различает character и UTF-8 byte offsets.
Прежние проверки полного source snippet, SHA/current snapshot, visible-source binding,
unresolved reference, partial coverage и запрета answer/edit выполняются также для этих positives.

19 новых public negative reads проверяют:

- другую phrase, обратный порядок слов, усечённое слово, иной регистр и отсутствующие обычные слова;
- условие, второе предложение, второй subject, второй `does` и другой auxiliary frame;
- перекрывающиеся identifier/phrase;
- удалённый identifier, иной raw case, heading/link-only, pair-only label,
  identifier-prefix, разные body units и перенос внутри phrase.

На настоящем count retrieval повторяются существующие 13 immutable/operational replay controls:
project/scope/catalog/hash/generation/freshness/window/body/raw-document/reference/admission forgery
и два operational veto. Ни source input, ни ожидаемый public факт не заменяются.
Первое cold чтение и все прежние fingerprint checks остаются на прежних местах.
После добавления ожидаются **11 positive + 39 negative reads = 50 state comparisons** внутри того же case;
это ожидаемый roster, а не уже полученный runtime PASS.

## Две направленные ошибки

| Mutation | Требуемый case:guard |
| --- | --- |
| Отключить новую count форму | closed_literal_context:recovery_count_literal_source_fact |
| При отсутствии целой phrase подставить zero-width match | closed_literal_context:recovery_count_phrase_body_witness |

Второй mutant сохраняет настоящий match на healthy positives, но делает отсутствующую phrase
допустимой при наличии identifier. Первый wrong-phrase public read обязан его отвергнуть.
Оба изменения действуют на исполняемый production source. Ошибка импорта, setup crash,
иной guard, пропущенный case или неполная baseline не считаются kill.
Все прежние 18 mutant blocks побайтно сохранены, оба новых anchors встречаются один раз.

## Manifest

| Path | Mode | Base blob | Proposed blob |
| --- | --- | --- | --- |
| docmancer/docs/domain/literal_context_admission.py | 100644 | 4d241f42fdfaf6dbf673cff05640097bbefaee72 | 219b8ea7fd644b901f888a51edb46e218b1973f9 |
| scripts/run_recovery_contract_gate.py | 100755 | 053c3cdf7405af5df61b85e5103fb42b82049466 | c3e21d5159cd67190134c951025a1b598b066781 |
| scripts/run_recovery_mutation_gate.py | 100755 | 97146ccb426a1775bbc9bd4601e3d8e76aca1aad | 8218799860c656e19a2a032ad7cc65b83c5ff45d |

Все три bases сверены на опубликованном SHA; blobs прочитаны обратно без расхождений.
Обратные narrow edits восстанавливают bases побайтно. Production 201 строк, recovery 872,
mutation runner 292 (включая завершающую пустую строку).

## Acceptance и открытая граница

Root source review 2026-10-10: APPROVE. Прочитаны production, оба существующих runners,
точные diff и зависимости `_relation_units`/`technical_term_pattern`; 18 old mutant blocks
сохранены побайтно. Нужны фактическая recovery baseline **12/12** и **20 intended kills**
на следующем опубликованном SHA, затем текущий P14 и обязательные совместные CI/downstream gates.
`policy_retry_count` ожидает настоящего повторного P14 прогона.
`alias_order_drafts` и `alias_project_retry_rule` остаются отдельными нерешёнными relevance cases:
этот контракт не восстанавливает их смысл и не меняет frozen questions/corpus/oracle.
Compound `Explain A and B` не входит в этот slice.
Локальные imports, AST, pytest и subprocesses не выполнялись; commits/refs агентом не менялись.
