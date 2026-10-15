# PR211: контекст для полностью указанного списка identifiers

Статус: independent static source review APPROVE; runtime нового slice pending.
Base: count-context slice `926cb5af417175a04d0752743171a56d75246a01`.
Исходные P15 question/corpus/gold, original-query qualification и output budgets не меняются.

## Причина

[Actual P15 на80c8](https://github.com/Vanilla1999/DocAtlas/actions/runs/38006157207/job/114075319048)
получил project fact37chars и library fact65bytes для исходного mixed question.
Same-call diagnostics показывают acquisition этих двух raw facts; прежние ошибки
provenance не наблюдаются. Public sources=[] и source_bindings=[], поэтому пустой
source_errors=[] не доказывает успешный mixed source binding: нужен actual delivery proof.
Project original qualification остаётся insufficient_visible_match1/4,
поэтому текущий project delivery veto блокирует mixed context.
Library fact не может дать project-role или original-query coverage credit.

## Узкий новый контракт

Поддерживается полностью потреблённая форма:

```text
Explain <bare technical identifier> [and <bare technical identifier> ...].
```

Сначала parser потребляет настоящий Explain frame, затем на каждой позиции
требует существующий unresolved/non-quoted QueryMention с isidentifier().
После каждого literal допускается только полный AND separator или завершающая точка.
Frame/separator могут иметь иной регистр; исходные literals и их координаты не меняются.
Любой неизвестный остаток, условие, второй predicate, OR или обычные слова
вместо technical literal отвергают новую форму целиком до выдачи первого witness.
Отсутствующие из-за действующей границы extraction mentions не превращаются
в частично принятую форму. Нового численного output ceiling нет.

Это не создаёт source/symbol role, не разрешает связи между названными сущностями,
не оценивает смысл или полноту ответа и не добавляет запросы для retrieval.
Старые closed What-does/What-is/requirements/count и quoted literal routes не меняются.
Existing negative `What does OrdersDraftStore and PaymentOutbox do?` сохраняется.

После прежних canonical project/member/scope/generation/hash/current/window checks
новый route разрешён только при insufficient_visible_match. Для каждого already-acquired
raw paragraph требуется неизменённая structural unit по _relation_units.
Все перечисленные exact literals удаляются для проверки содержательного остатка:
голые имена не могут служить содержанием друг для друга.
Затем возвращаются только literal occurrences, реально присутствующие в этом абзаце.

Normalized units используются только для структурной проверки.
Каждый source/query span вычислен из исходного текста. Titles, headings, link-only
и identifier-only labels не дают witness новой ветке. Incoming flags и scores
не дают права обойти canonical source/lifecycle recheck.

Результат — source-bound partial context. query-original остаётся missing,
original trace unqualified, coverage_credit=False; answer_supported,
answer_available и edit_ready остаются False. Unified delivery eligibility
и library version/current/source guards не изменены.

## Независимый existing-case oracle

Новых ordinary test functions или recovery cases нет.
В существующий closed_literal_context добавлены два non-P15 source facts:

```text
λ entry. DeliveryEpoch retains three rollover phases.
λ entry. CommitLatch preserves nine checkpoint records.
```

Каждый real read получает только один такой документ. Пять positives проверяют
оба identifiers по отдельности, оба порядка и uppercase EXPLAIN/AND,
а также список из трёх имён, у двух из которых нет source fact.
Прежние full snippet/current SHA/source binding/immutable fingerprint/no-grant
guards выполняются для каждого read. Независимый str.index oracle требует,
чтобы ВСЕ witnesses имели именно ожидаемые raw/query spans и literal;
отсутствующее в body имя не может получить заимствованное свидетельство.
λ до identifier различает character и UTF-8 byte offsets.

15 negatives сохраняют отказ на unsupported whole-frame syntax и отсутствующем,
wrong-case, heading/link/identifier-only/prefix body.
Отдельный pair-only body с двумя bare names проверяется вопросом из трёх names:
2/5<0.5 сохраняет canonical insufficient_visible_match и изолирует новую ветку.
Тест не меняет общий lexical qualifier ради отказа, который тот уже считает qualified.

На первом real Explain retrieval повторяются все13 существующих immutable
и operational replay faults. После count+Explain ожидается
16 positive +54 negative =70 state comparisons внутри того же case.
Это ожидаемый roster; actual runtime ещё не получен.

## Направленные дефекты

| Mutation | Первый требуемый guard |
| --- | --- |
| Отключить весь Explain route | recovery_explain_literal_source_fact |
| Игнорировать непрочитанный хвост | recovery_explain_complete_syntax |
| Удалить для substantive check только первое имя | recovery_explain_exact_body |

Третий fault сохраняет здоровые факты и прежний single-label negative,
но позволяет второму имени в pair-only body изображать содержательный остаток.
Это конкретный дефект, найденный source review, и его собственный intended kill.
Production anchors должны встречаться ровно один раз.
Все20 прежних mutants побайтно сохраняются, все12 recovery case names прежние.
Цель следующего actual run: **12/12 baseline +23 intended kills**,0ERROR/SKIP.
Baseline failure, setup exception или другой guard не считается kill.

## Review и граница evidence

Первый independent review нашёл два дефекта до публикации: uppercase frame
ошибочно становился technical mention; удаление только одного имени давало
другому имени роль содержательного остатка. Оба исправлены в parser/body guard;
positive uppercase case сохранён и усилен uppercase AND, body control добавлен.
Runtime12/18 на80c8 не доказывает новый route; pending count12/20 тоже не actual.

| Path | Mode | Base blob |
| --- | --- | --- |
| docmancer/docs/domain/literal_context_admission.py | 100644 | 219b8ea7fd644b901f888a51edb46e218b1973f9 |
| scripts/run_recovery_contract_gate.py | 100755 | c3e21d5159cd67190134c951025a1b598b066781 |
| scripts/run_recovery_mutation_gate.py | 100755 | 8218799860c656e19a2a032ad7cc65b83c5ff45d |

Root и independent reviewer APPROVE финальные production/oracle/mutants;
третий pair-label fault отдельно рассмотрен после обнаруженного дефекта.
Все source и runner bases/anchors сверены, roundtrip совпадает; старые20 mutants
сохранены. На следующем SHA нужны собственный recovery proof, настоящий P15 mixed delivery,
полный core и required/downstream gates. Source filename-binding для второго
remaining P15 case — отдельный contract/slice.
Локальные AST/import/pytest/runtime не запускались; новая runtime проверка —
существующий разрешённый PR CI.
