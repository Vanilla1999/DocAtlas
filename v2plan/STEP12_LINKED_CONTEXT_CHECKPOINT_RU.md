# Step 12: связанные условия после отбора и проверка черновика

Дата: 7 ноября 2026, Europe/Moscow.
Проверенная исходная main: `b1eba6c677d91dd60af570d18877b038992431f7`.
Предыдущие PR246 и PR247 уже merged. Ветка реализации:
`work/step12-linked-context-20261107`.

## Разрешение и границы изменения

Новое поручение владельца: после merge предыдущей работы реализовать
дополнение выбранного правила связанными условиями, различение прямых ссылок
и ссылок предков/навигации, явные незакрытые зависимости и проверку черновика
по источникам в лёгком клиенте. Словари синонимов, названий разделов,
question-to-file rules, aliases и позиционные таблицы расшифровки запрещены.

Новый host-only `DOCATLAS_CONTEXT_LINKS=one-hop-v1` применяется **после**
неизменённого Qwen v1 scoring/threshold. Default `off` сохраняет прежний путь,
scoring inputs, policy и continuation fingerprint. Включение допустимо только
с `DOCATLAS_EXPERIMENT_MINIMAL_CONTEXT=1` и
`DOCATLAS_MINIMAL_CONTEXT_RECIPE=qwen3-contextual-own-body-evidence-v1`.
Неверное сочетание отвергается, не превращается в молчаливый fallback.

Новые ссылки рассматриваются только в собственном тексте выбранных разделов.
Добавленные разделы и вводные части предков не становятся новым frontier.
Навигация определяется синтаксисом, не списком слов. Адресованный раздел
добавляется исходным текстом вместе с предками, с прежней проверкой source,
hash, scope и same-call provenance. Адрес документа без якоря не означает
разрешения выдать весь документ. Непройденные, неоднозначные и недоступные
ссылки, а также недоставленные потомки отмечаются явно. Ссылка сама по себе
не даёт права чтения. Полнота ответа остаётся `unverified` даже при отсутствии
обнаруженных незакрытых ссылок; условий без ссылок этот механизм не находит.

Общий prompt MCP/files получает уже исследованную проверку черновика по
источникам без названий ожидаемых фактов и без обязательного дополнительного
вызова модели. Это не гарантия сохранности всех условий.

## План проверки, зафиксированный до исполнения

Исторические вопросы, gold, policies, Qwen outputs и blind-260 не изменяются.
Новых unit tests/строковых матриц нет. Повтор только после конкретного дефекта
или изменения проверяемого кода; первый сбой и фактические calls сохраняются.

1. **Seen-development structural replay.** Одна реальная подготовка исходного
   Meridian scope-каталога (6 project documents и исходный исключённый module
   document), четыре исходных V-M1…V-M4 через public `get_docs_context`.
   В пассивном return-hook существующего native projector, пока жив same-call
   receipt, выполнить baseline/off и one-hop на одних и тех же checked units.
   Seeds — только сохранённые реальные scores Qwen и frozen threshold,
   сопоставленные по path + hash + char span. Неполное сопоставление — BLOCKED,
   не oracle substitution. Итого 1 prepare, 4 context, 8 closures, 0 model,
   0 resource calls. Независимо проверить факты, exact slices, scope, hashes,
   неизменность базы/источников и отказ expired provenance после вызова.
   Это component integration внутри реального retrieval, **не** публичный
   финальный Qwen packet и **не** fresh model acceptance.
   Дополнение до запусков: исходные четыре вопроса не покрывают navigation,
   ancestor-only links, depth-limit и direct scope denial. Один отдельный
   компактный guard scenario на основе существующего
   `probe_minimal_structure.DOCUMENTS/QUESTION`: 1 prepare + 1 context,
   0 model calls. Явно заданный раздел Selected здесь является входом
   структурной стадии, не результатом подменённого scorer. Исторический fixture
   не меняется; ожидаемые source facts и исключённые тексты записываются до
   исполнения. Проверяются прямой target, ancestor/navigation не как frontier,
   pending second-hop/missing anchor/document target, scope и exact bytes.
2. **Public configuration/default regression.** Переиспользовать существующий
   публичный continuation scenario; invalid link mode / disabled minimal /
   incompatible recipe проверить через настоящий CLI/server startup, без
   подмены scorer. Зафиксировать число запросов. Новый on/off continuation
   с настоящим Qwen отдельно BLOCKED, пока недоступен pinned runtime.
3. **Fresh installed wheel.** Сверить packaged product bytes. Существующий
   isolated stdio smoke: 1 prepare, 2 context, 1 resource, 0 models; default/off,
   положительный факт и version denial. Исторический manifest не менять.
4. **Настоящий OpenCode 2.2.5, внешний scripted provider.** Существующий
   `check_profile_client.py`: два сеанса MCP/files, до4 и до2 provider requests,
   реальные tools/read denials, неизменный вопрос/AGENTS/scope и точный audit
   paragraph в первом system prompt. Драйвер также делает 1 prepare и
   1 canonical context. Проверяет доставку инструкции, **не** её исполнение
   реальной моделью. Новый baseline inventory и новые answer generations
   не требуются для изменения одной инструкции.
5. Whitespace/module-size, независимый review нового link parser, scope и
   публичной metadata. Исправления не должны менять замороженный scorer.

## Доступность runtime

В свежей среде нет GPU/CUDA, pinned Qwen/MiniLM assets и настроенного
авторизованного answering endpoint. Pinned Qwen требует CUDA12.8,
capability12.0, torch2.10.0+cu128, transformers4.57.1, tokenizers0.22.2,
safetensors0.8.0 и точные model hashes. CPU fallback контрактом не допускается.
Обычные/dev зависимости устанавливаются из lock. Платный GPU/provider,
ослабление model/runtime checks и подмена Qwen другой моделью не разрешены
этим планом. Fresh Qwen, MiniLM, Terra и end-to-end answer quality будут
отмечены NOT RUN/BLOCKED, если runtime не появится.

## Результаты

Существующий default continuation scenario: 1 PASS, 2 подготовки,
13 context requests, 2 source reads, 0 inference; 2,90 с. Изменений вопросов,
ожиданий и default path для этого результата не было.

Первый structural `run-01`: **BLOCKED**, не общий PASS. Фактически
2 prepare + 5 context + 6 closure calls + 0 models + 0 resources.
V-M2 сохранил 6/6, V-M3 — 5/5; no new evidence там не требовалось.
Guard: 3/7 → 7/7, запрещённые ancestor/navigation/second-hop/module и неверный
HTML target не выданы, 8 pending references явны. Source/DB unchanged;
32 row rechecks и 6 expired-provenance denials прошли.

V-M1 и V-M4 вернули обычный `context_only` до native projector; callback не
вызвался. Старый Qwen protocol передавал те же русские original questions
без переводов/lookups, но использовал complete-scope acquisition. Наш обычный
немодельный public route проходит lexical admission. Это ограничение replay,
а не установленная регрессия нового closure, который на этих двух вопросах
не выполнялся. Ни missing units, ни вопросы/lookups ради PASS не заменяются.

Дополнительный ограниченный guard rerun разрешён после двух конкретных
static-review исправлений: (1) прямой переход в уже выданного предка не должен
переименовывать его origin в linked_body; (2) маскирование inline code не
должно превращать HTML attribute в другой literal target/anchor — такой
синтаксис явно отклоняется с сохранением исходного адреса. В том же guard
добавляются source-authored witnesses; только 1 prepare + 1 context,
2 closure calls, 0 inference. Четыре Meridian-вопроса не повторяются.
Первый run и его manifest сохраняются. Новая сборка wheel делается после
этих исправлений; первая сборка не используется для client acceptance.

Final guard run-02: PASS_STRUCTURAL_REPLAY_ONLY, 1 prepare + 1 context +
2 closures; 3/7→7/7, 12 row rechecks, 2 expired-provenance denials,
source/DB unchanged. 10 pending references не скрыты. V-M1/V-M4 не повторялись.
Токены источников 182→252, reconstruction packet692→1345; это не billing
и не свидетельство средней экономии. Общие structural calls двух запусков:
3 prepare + 6 context + 8 closures + 0 inference.

Fresh final wheel: SHA256
`da1f97ffadd501d40457a170bebc777f9c253464aa3141649a32eae3230a17c4`.
457 packaged files сверены с checkout и isolated installation, 441 Python
modules включены, missing/mismatches0. Installed SDK stdio default/off PASS:
1 prepare + 2 context + 1 resource, source/version/state guards сохранены.
Три real CLI startup denials PASS для неправильной links configuration.

Real OpenCode2.2.5, external scripted provider: первая попытка PASS,
MCP4 + files2 requests, errors0, 0 model inference. Audit paragraph действительно
в first system обоих профилей; scope/denied reads, original question/AGENTS,
неизменность sources/DB проверены. Это delivery acceptance, не качество ответа.
Shared prompt265→313 local o200k tokens (+48). Текущий harness внутри checkout
наследовал также его AGENTS.md, поэтому абсолютные system counts не являются
чистым сравнением с прошлым внешним fixture.

Независимый review выполнен; HTML double decode, origin и mask findings
исправлены и отражены в guard. Whitespace/module-size PASS. Полный отчёт:
`reviews/STEP12_IMPLEMENTATION_RU.md`. Ни fresh Qwen/MiniLM/Terra, ни новый
общий19/19, ни полный CI PASS не заявляются. PR/merge подтверждаются отдельно.
