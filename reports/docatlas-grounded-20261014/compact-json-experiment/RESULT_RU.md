# C: компактный JSON при повторной упаковке и доставке — измеренный FAIL

## Итог

Компактная сериализация **реально изменила first-fit selection**, добавив пять
окон P03 и четыре E01, но не вернула обязательные поздние окна. Полнота обоих
случаев остаётся FAIL. Вариант остановлен, новый V40 **не запускался**.
Это не прежняя пересериализация готового ответа и не learned selector B.
B остаётся BLOCKED; поиск моделей, inference и обучение не выполнялись.

До начала и после эксперимента remote head ветки
`integration/stage3-v2-identity-pr1` —
`cd9c52347fc9d02b6be788017249f6cc62ec2cda`. Рабочее дерево до начала было чистым.
AGENTS.md прочитан. Новые изменения не откатывались; main, PR и remote не менялись.
Прототип и отчёт **не закоммичены и не запушены**.

## Изолированный opt-in и граница проверки

- `docmancer/docs/application/context_json.py`: host-only переключатель
  `DOCATLAS_EXPERIMENT_COMPACT_CONTEXT_JSON=1`, только для `docs_context`.
  Default остаётся прежним `json.dumps(payload, ensure_ascii=False)`.
- C: `ensure_ascii=False, separators=(',', ':')`, без сортировки ключей.
  Меняется только JSON whitespace вне строк, не DTO-поля и не исходный текст.
- `experimental_context_cost` и MCP `_json_text` используют **один serializer**.
  Поэтому он применяется при каждом добавлении целого окна, при окончательной
  проверке после регистрации references и в фактическом MCP TextContent.
  Поле `estimated_tokens` и остальные значения DTO для одного набора не меняются.
- Не менялись first-fit, ranking, admission, source validators, native windows,
  read-only policy, cap12000 и tokenizer. Не использовались neighbors/boosts/gold
  при отборе. Retrieval и validators не подменялись.

Установлен **non-editable** пакет в `/tmp/opencode/docatlas-compact-runtime`,
Python3.13.12 `-I`, MCP SDK1.29.0. Все416 installed product files побайтно совпали
с checkout. До выполнения заморожены463 input files, включая код, документы,
вопросы, oracle, evaluator, lockfile и pilot; после выполнения все совпали.
Head описывает опубликованную базу, а hashes и diff в FREEZE — локальный прототип.

**2 реальные подготовки, 4 get_docs_context calls**, без retries. По одному
stdio-серверу и общей SQLite/generation/root на case; P03 A→C, E01 C→A.
Использованы production `_run_async`, реальный SDK `ClientSession`,
`list_tools` и `call_tool`, host text-fallback `DOCATLAS_MCP_TEXT_FALLBACK=1`.
Клиент сохранил доставленный текст, а не заново сериализованный dict.
SDK декодировал ответы без смены публичной схемы. Это installed stdio/client
integration, не production smoke и не проверка всех сторонних клиентов.

Переключение A/C выполнялось только в последовательном экспериментальном
server harness на входе исходного публичного вызова. В production opt-in —
настройка процесса; динамическое переключение при concurrent calls не проверено.
Пассивная трасса одинакова по механизму для обоих arms, не изменяет operands.
Gold/evaluator открывались только после доставки всех четырёх ответов.

## Парные результаты на фактически доставленном полном DTO

Cost = `max(o200k_base(JSON), ceil(UTF8(JSON)/4))`, cap **12000**.

| Case | Arm | Обязательные символы | Окон | UTF-8 bytes | UTF-8/4 | Codec / полный cost | Integrity / read-only |
|---|---|---:|---:|---:|---:|---:|---|
| P03 | A |442/515, FAIL|42|36876|9219|11862|PASS / PASS|
| P03 | C |442/515, FAIL|47|39455|9864|11982|PASS / PASS|
| E01 | A |0/557, FAIL|39|36565|9142|11865|PASS / PASS|
| E01 | C |0/557, FAIL|43|38773|9694|11846|PASS / PASS|

Компактный формат не обязан снижать **конечный** cost: first-fit заполняет
освободившийся бюджет другими окнами. P03 C содержит больше bytes и tokens, чем A.
Исходный P03 witness `[2805,3320)` всё ещё теряет `[3247,3320)`; E01 полностью
теряет `[584,1141)`. Полные required windows присутствовали до terminal packing.

Эти A — новые парные измерения, не исторические11884/11819 и41/39 окон.
Новые root/identity/hash values меняют JSON и его BPE cost; сравнение C проводится
только с A на **том же** root/generation, не с историческим fixture.

## Нужные окна: позиция и причина исключения

Позиции — 1-based в неизменном полном admitted pool167/256; chars — полуоткрытые.
Каждая стоимость — реально выполненная попытка полного DTO, не стоимость snippet.

| Case / окно | Chars / lines | Позиция | A: cost / выбранных до попытки | C: cost / выбранных до попытки | Результат A/C |
|---|---|---:|---:|---:|---|
| P03 правило |2805–3247 /102–111|10/167|2943 /9|2668 /9|retained / retained|
| P03 пример |3247–3446 /112–121|74/167|12107 /42|12032 /46|over cap / over cap|
| E01 имена |584–993 /19–29|137/256|12173 /39|12130 /43|over cap / over cap|
| E01 размещение/пример |993–1324 /30–45|141/256|12173 /39|12130 /43|over cap / over cap|

Для пропущенных нужных окон каждая recorded trial превышает12000; IDs есть в
полном omission ledger. У P03 C нужный пример превышает cap на32 tokens, но это
FAIL, не основание увеличить бюджет или поменять oracle. First-fit не заменяет
ранние выбранные окна: экономия была занята раньше нужного дополнения.

## Какие окна добавились

Все прежние выбранные A окна остались: **исчезнувших нет**.
Ниже приведены все изменения, не только целевые окна. Полные DTO rows, IDs,
snippet hashes и executed trial receipts находятся в MEASUREMENTS/архиве.

| Case | Позиция | Исходный документ / lines | A trial cost | C trial cost |
|---|---:|---|---:|---:|
| P03 |43|`docs/configuration.md`602–612|12132|11068|
| P03 |44|`docs/configuration.md`298–309|12125|11307|
| P03 |45|`docs/configuration.md`653–662|12142|11563|
| P03 |46|`docs/configuration.md`706–716|12134|11811|
| P03 |100|`docs/configuration.md`179–180|12057|11982|
| E01 |40|`docs/src/use/configure/ignore.md`152–160|12152|11159|
| E01 |41|`docs/src/use/configure/configuration-files.md`782–785|12135|11405|
| E01 |42|`docs/src/use/command-line-interface.md`983–984|12099|11615|
| E01 |43|`docs/src/use/configure/configuration-files.md`326–327|12120|11846|

Причина каждого добавления: в A точный trial был over cap, в C стал допустимым.
Наборы предыдущих retained windows после первого расхождения уже различаются;
эти cost deltas нельзя считать изолированной whitespace-экономией одного набора.

## Время выполнения

| Case | Server A→C, seconds | Изменение | Client round-trip A→C, seconds | CPU A→C, seconds |
|---|---|---|---|---|
| P03 |27.1201→27.2352|+0.1151 (+0.42%)|27.1712→27.2813|27.0535→27.1819|
| E01 |36.7458→38.9836|+2.2378 (+6.09%)|36.8141→39.0602|36.6810→38.9195|

Это фактически наблюдённое изменение на **одном** вызове каждого arm с одинаковой
пассивной instrumentation, не uninstrumented latency benchmark, confidence
interval или доказательство причинности. Client time включает protocol/receipt
overhead; server time — исполнение публичного handler с profiler. C выполнял
проверки большего retained набора. Повторных performance-прогонов не делалось.

## Integrity, неизменность и доказательства

- Все search/acquisition/admitted selection/native projection/project projection
  operands A/C равны целиком, включая порядок и binding values.
- Для всего pool167/256 независимо проверены исходный raw SHA, exact snippet
  bytes/hash, char range и равенство reference/visible whole-window spans.
  Каждый delivered row равен исходному row из pool, metadata не удалена.
- Scope=`project`, version=`unversioned`, source identity/authority и line spans
  проверены по исходным документам. Production validators продолжали работать.
  `content_sha256` DTO — projection fingerprint, не raw-file hash: он сохранён
  из проверенного pool; raw hashes проверены отдельно по SQLite generation sources.
- Read-only4/4: project file hashes и логическое содержимое **всех SQLite tables**
  до/после каждого context call равны. Побайтная неизменность SQLite/WAL не заявлена.
- Клиент проверил обе независимые составляющие full budget по actual TextContent.
  Все observed trials имеют точный codec/proxy cost; final wire SHA совпадает
  с финальным budget operand. Stderr отдельно от protocol stdout; observer errors0.
- Неизменённый evaluator SHA:
  `32cf91a78807d1cb5709edb140cc1ff62ad4027023cb4a382c702403188921fa`;
  gold SHA: `3a78745249900056d98870850add167e9cc0ceaeb284e0db759b78b94303eacc`.

`FREEZE.json`, `MEASUREMENTS.json`, `EVIDENCE_AUDIT.json`, `GATES.json` и
`RECEIPTS_ARCHIVE.json` — открытые receipts. `receipts.tar.xz`291472 bytes,
24 файла: complete traces/trials, actual client DTO text и MCP results,
independent oracle receipts, preparation inventories. Все SHA-256 проверены.

Новый V40 и strict-empty negatives не измерялись: pilot gate FAIL.
Исторический strict-empty0/8 не является новым результатом C и не доказывает
semantic refusal. Два development cases не являются holdout. Общая проблема
выбора контекста **не объявляется решённой**.

## Воспроизведение без замены исходных эталонов

Использовать fresh work/output, не перезаписывать измеренный запуск:

```sh
UV_PROJECT_ENVIRONMENT=/tmp/opencode/docatlas-compact-runtime uv sync --frozen --no-dev --no-editable --reinstall-package doc-atlas
TMPDIR=/home/viadmin/.cache/docatlas-budget-private-20261014 HF_HUB_OFFLINE=1 /tmp/opencode/docatlas-compact-runtime/bin/python -I reports/docatlas-grounded-20261014/compact-json-experiment/pilot.py --repo "$PWD" --work /tmp/opencode/docatlas-compact-fresh-work --output /tmp/opencode/docatlas-compact-fresh-output
/tmp/opencode/docatlas-compact-runtime/bin/python -I reports/docatlas-grounded-20261014/compact-json-experiment/assess.py --repo "$PWD" --run /tmp/opencode/docatlas-compact-fresh-output --output /tmp/opencode/docatlas-compact-fresh-output/EVIDENCE_AUDIT.json
```

На другом host выбрать TMPDIR с private/безопасными ancestors: общий
`/tmp/opencode` mode775 не проходит member-storage policy. Менять эту policy
ради запуска нельзя. Новые пути требуют нового FREEZE и могут менять costs/IDs.
V40 не запускать для этого FAIL-варианта; параметры и эталоны не подгонять.
