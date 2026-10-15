# PR211 — независимые controls перед simplification

Дата: 2026-10-06. Worktree: `/tmp/opencode/pr211-simplify-controls`.
Ветка: `diagnostic/pr211-simplify-controls-20261006`.
Baseline/HEAD: `37bfd0668f819935dd9e027bd9d8bf767fcd185a`.

## Итог

Подготовлены **10 native public-pipeline captures**, не «10 PASS»:
семь A-контролей, две исследовательские B-пробы, один настоящий projection crop.
**B-пара отвергнута как discriminator:** явно запрошенный supporting-факт релевантен,
но supporting естественно принимается раньше authoritative. Доказательства
безопасности/небезопасности расширенного `authority_duplicate` эта пара не даёт.

Ключевой A-контраст воспроизведён: `missing_attribute` одинаково возникает без числа
и при настоящем числе с разделёнными термами; чужое число в той же фразе получает
валидный local proof. Это наблюдения detector, **не gold**. Baseline доставляет все
заданные положительные факты. Product patch в этой работе не испытывался.

## Артефакты и native seam

- `controls_corpus.py`: вопросы, реальные source bytes, ожидаемые цитаты,
  запрещённые claims, желаемый admission и открытые контрактные вопросы.
- `run_controls.py`: standalone runner вне `tests/`, без регистрации нового gold.
- **`controls-final-baseline.json` / `.log`**: окончательные 10 cases.
- `controls-baseline.json` / `.log`: первая итерация, включая отвергнутый crop
  653 → 653 и первоначальный A1 без соседнего OtherWorker.
- `controls-crop-recheck.json` / `.log`: адресная проверка исправленной crop-fixture.

A/C используют существующий `capture_reference_case` → `capture_fixture` → native
ingestion → `capture_public_call` → настоящий transport-validated
`call_docs_tool_payload`. B использует тот же native runtime и публичный capture,
с source-of-truth/supporting manifest из исходной notes fixture. Manifest создаётся
только внутри временного corpus; существующие manifests не менялись.
24 notes сохранены из исходной B-fixture, а не добавлены ради изменения ranking.

Dispatcher, qualification, ranking и final packet не подменяются. Два observers
делегируют исходным функциям и возвращают их результат без изменения:
существующий projection capture и локальная обёртка
`_answer_units_part02.local_proof_for_obligation`. Последняя фиксирует фактически
выполненные вызовы из `best_local_proof`; одинаковые записи агрегируются с `calls`.
Это не обещание перехватить каждый отдельно импортированный alias proof-функции.

JSON сохраняет question/lookup → component contract → исходные документы и
pre-projection context → реальные local proof decisions → selection traces →
полный final packet/snapshot. Проверяются лимиты 800 tokens / 3 sources, verbatim
строки и snapshot integrity; исходные fixtures сохраняют собственные assertions.
Нет assertions, требующих определённого `LocalProof.valid`, `missing_attribute`,
covered query ID либо отказа вместо полезного факта.

## Минимальная acceptance-матрица

Общий A-вопрос: `How many retry attempts does ProjectRetryPolicy allow?`
Все источники локальные, актуальные и безопасные по fixture; допустимость источника
как кандидата отдельно от полезности конкретного контекста и proof ответа.

| ID | Источник / отличие | Желаемая доставка из вопроса и source | Baseline / ограничение |
|---|---|---|---|
| A0 no-value | `ProjectRetryPolicy delegates retry decisions to OtherWorker.` | Числа нет. Предпочтителен strict отказ; число/полноту ответа утверждать нельзя | `ok`, delegation виден; main-path `missing_attribute`; публичной answer authority нет. Refusal preference не выполнена, но это не новый согласованный gold |
| A1 inline exact / own vs other | `ProjectRetryPolicy allows at most two retry attempts, while OtherWorker allows nine retry attempts.` | Сохранить собственный факт **at most two**, привязанный к ProjectRetryPolicy; девять относится к OtherWorker | Собственный факт доставлен; exact attribute witness распознан |
| A2 heading exact | `# ProjectRetryPolicy` + `The policy allows at most two retry attempts.` | Доставить heading и числовую фразу вместе в одной цитате | Оба доставлены; witness распознан |
| A3 inline split | `ProjectRetryPolicy retry policy allows at most two attempts.` | Сохранить полный явно привязанный числовой факт | Доставлен, хотя main-path `missing_attribute` |
| A4 heading split | `# ProjectRetryPolicy` + `The retry policy allows at most two attempts.` | Сохранить heading и числовую фразу вместе | Доставлены, хотя main-path `missing_attribute` |
| A5 other subject same sentence | `ProjectRetryPolicy delegates retry decisions to OtherWorker, which allows nine retry attempts.` | Нельзя переносить **nine** на ProjectRetryPolicy. Предпочтение отказа требует отдельного решения по partial context | Фраза доставлена основным путём, local proof valid. Это не наблюдаемая ложная публичная answer authority |
| A6 explicit independent lookup | A0 + `The diagnostic command for ProjectRetryPolicy is ` + `` `inspect-retries` `` | Для явного lookup о diagnostic command желательно сохранить команду; numeric answer по исходному вопросу остаётся неизвестным | Команда доставлена; `missing_attribute`; lookup и original публично missing. Доставка и attribution здесь расходятся |
| B0 distractor | Исходные notes без warning + authoritative plan; вопрос явно спрашивает contract **и warning** | Сохранить normative contract из plan, не выдавать mentions за warning. Notes желательно исключить | Contract и note доставлены. Supporting принят первым: **непригоден для B authoritative-first проверки** |
| B1 requested supporting fact | Тот же вопрос/manifest; в notes добавлен явный warning | Сохранить contract из plan и ``When decision_hash changes, the presentation shows the red warning `Decision changed`.`` из supporting | Оба факта доставлены; supporting принят первым. Факт релевантен, но **контроль B отвергнут: authoritative-first отсутствует** |
| C0 actual crop | A1-подобный собственный numeric факт без OtherWorker + длинный prose paragraph | При содержательном crop сохранить `ProjectRetryPolicy allows at most two retry attempts.` | Вход projection **772 chars**, final **462 chars**; факт сохранён, tail proposition удалён |

Для A1 требуются собственный subject/предикат/число, а не сохранение ненужного
соседнего числа. A2/A4 требуют локальную совместную доставку heading и body.
Для B допустимы разные источники для разных фактов: `same_source` к этой паре
не применяется. Все обязательные quoted facts находятся в `required_visible`;
это acceptance на доставку verbatim material, не downstream ответ LLM.

### Запрещённые claims и открытый контракт

1. По существующему retrieval-only контракту (`docs/mcp-docs-server.md:42–47`)
   `docs_context` не даёт answer/edit authority. Во **всех** финальных captures
   `answer_supported=false`, `answer_available=false`, `edit_ready=false`,
   `facet_coverage=unverified`, `facets=[]`.
2. A0/A5/A6 не содержат requested count. Нельзя утверждать собственный numeric
   ответ ProjectRetryPolicy либо семантическое покрытие этого count. У A5
   `retrieval_coverage=full`; по `coverage_policy=retrieval_attribution_only`
   это **не** утверждение семантической полноты. Не запрещаем full retrieval по догадке.
3. В B1 supporting описывает запрошенное наблюдаемое warning, но прямо не определяет
   normative acceptance contract. Нельзя повышать authority note до source_of_truth.
   В B0 warning вообще отсутствует, даже если retrieval coverage full.
4. Жёсткий отказ на A0/A5 — **желаемое строгое поведение, не утверждение действующего
   общего контракта**. Frozen module adversarial здесь не переписывается и не
   воспроизводится; перенос его refusal gold на всякий project partial context
   требует owner agreement. A6 также оставляет открытым veto полезного explicit lookup.
5. Recall A1–A4 имеет прямое source/question основание. Потерю этих фактов нельзя
   оправдать одним detector verdict. Для candidate это самостоятельный блокер,
   если owner явно не согласовал recall tradeoff.

## Что именно различают observations

Для полных числовых answer units A3/A4 observed local scores:
subject **3**, attribute/relation **0**, number **2**, valid **false**.
A0: **3/0/0**, valid false. A5: **3/3/2**, valid true.
Таким образом, отсутствие witness не доказывает отсутствие числа; co-occurrence
не доказывает принадлежность числа. Эти значения записаны как observations,
не используются runner как желаемый verdict новой реализации.

B не исправлялся подбором weights, перестановкой sources или parser exceptions.
Фактические `selection:accepted` события сопоставлены с native candidate identities:
сначала `docs/note-*` (supporting), затем `zz-authoritative-plan.md` (source_of_truth).
План неполный в обеих пробах. Номер note недетерминирован среди одинаковых docs;
это не ranking gold. **Авторитетный-first request-relevant positive по B всё ещё отсутствует.**

C0 сравнивает один реальный входной context window с final bytes, с тем же path,
project identity и contiguous substring; сохраняет stable chunk ID, source snapshot,
final evidence ID и обе строки. В final исчезает целая фраза
`The diagnostic archive stores completed request logs for later operator inspection.`
Она присутствовала **до projection**, а не только в полном файле. Бюджеты не менялись.
Первый вариант 653 → 653 честно оставлен как rejected crop attempt. C0 проверяет
сохранение requested fact при удалении ненужного prose; не доказывает корректность
атрибуции после удаления самого witness, anchor-only admission или heterogeneous merge.

## Команды и результаты

Из указанного worktree:

```sh
export DOCATLAS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export PYTHONPATH=/tmp/opencode/pr211-simplify-controls
PY=/home/viadmin/StudioProjects/hermes/docmancer/.venv/bin/python
$PY run_controls.py --output controls-baseline.json > controls-baseline.log 2>&1
# После уточнения только crop corpus: адресная перепроверка.
$PY run_controls.py --case C0_real_projection_crop --output controls-crop-recheck.json > controls-crop-recheck.log 2>&1
# Окончательный корпус, включая competing subject в A1:
$PY run_controls.py --output controls-final-baseline.json > controls-final-baseline.log 2>&1
git diff --exit-code HEAD -- docmancer tests eval docs v2plan
git diff --check
```

Все перечисленные команды завершились **exit 0**. Python **3.13.12**.
У runner exit 0 означает завершённый capture и инфраструктурную валидность,
а не acceptance; итоговый stdout явно отказывается от aggregate PASS count.
Финальная сводка JSON дополнительно сверена: 10 rows, все required facts доставлены,
authority flags false, actual crop true, B authoritative-first false в обеих пробах.

SHA-256 финальных файлов:

- corpus: `27b5eb5c481642bad9c88e4a3ac04022882ada973eea01304bcd95aad6bd9c14`;
- runner: `f07e3572e36ca055cf972c4ce65c508245eae3e3bb1d7295f62ff5d5d8bcbfa0`;
- product projector: `3fabbd99b47bb964d253dea96f7ada5d88001e554d1426d4873ee8cfa683103d`.

Для будущего разрешённого simplification diff на этом baseline runner принимает
`--label proposal-name --output controls-proposal-name.json`; сам patch не создаёт.
Сопоставлять следует неизменный corpus hash, required quotes/их subject binding,
authority flags и actual pre/post windows. Изменение proof verdict само по себе не
регрессия и не успех. Для A0/A5/A6 сохраняется отдельный owner contract decision;
B precondition failure нельзя засчитывать как проверку безопасности candidate.

Прочитаны requested reassessment, independent reviewer report, `reviewer_A_formats.py`
и исходные A/B/C reports read-only. Full suite не запускался. Все изменения — новые
standalone файлы в этом worktree; tracked product/tests/gold/manifests неизменны.
Другие worktrees не редактировались. Commits/push/merge не выполнялись.
