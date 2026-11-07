# Шаг 11: что реализовано в пунктах 3 и 4

7 ноября 2026. База изменений: `2d667913`. Поручение владельца: реализовать
лёгкий клиент и буквальный вывод, объединить накопленную ветку с main, затем
отдельно исследовать сохранение условий и полноту конечного ответа.

## Практический результат

Добавлен явный клиентский профиль **documentation-light-v1**. Он подключает
подготовленный проект к OpenCode, оставляет поиск документации, статус проекта
и чтение выданных источников, использует короткую общую инструкцию и сохраняет
применимые AGENTS. Исходный вопрос не переписывается. Выбранный режим поиска
сохраняется: MiniLM, Qwen, E5 автоматически не включаются.

Подключение описано в
[DOCUMENTATION_PROFILE.md](../integrations/opencode-v2-compact/DOCUMENTATION_PROFILE.md).
Генератор создаёт отдельную конфигурацию и отказывает при попытке перезаписать
существующую. Новый профиль ограничен project scope. Файловый backend — отдельный
диагностический контроль для конечного изолированного корпуса, состав и хеши
которого проверяются до и после вызовов. Он не объявлен эквивалентом произвольного
репозитория или всех правил доступа MCP.

На стороне сервера добавлен явный **DOCATLAS_CONTEXT_PRESENTATION=literal-v2**.
Поддерживаемый успешный initial docs_context содержит обычные JSON-объекты
источников: исходный текст, полные references, пути, строки, scope и trust notice.
Позиционных таблиц, коротких aliases и смысловых словарей нет. Per-source
content_sha256 не показывается модели; canonical packet и серверные проверки
hash/access/snapshot/expiry остаются. Patch, source-read, ошибки и неподдерживаемые
формы сохраняют прежний контракт. Без флага и при off поведение историческое.

Код: профиль — `integrations/opencode-v2-compact/documentation_profile.py` и
`profile/`; представление — `docmancer/docs/domain/context_presentation.py` и
`docmancer/docs/application/standalone_text_view.py`. Revision участвует в
continuation binding и фактической оценке размера доставки.

## Что показали измерения

| Измерение | До | После | Вывод |
|---|---:|---:|---|
| Первый готовый запрос клиента, system + tools | 2382 | 2135 | −247 локальных токенов, −10,37% |
| Файловый контроль, такой же показатель | — | 1251 | По этому показателю файлы пока дешевле MCP |
| Один ordinary packet в клиентском примере | 447 | 447 | Экономии от literal-v2 здесь нет |
| Другой ordinary packet, четыре источника | 555 | 584 | Обычные объекты длиннее адаптивной таблицы |
| Сумма 16 сохранённых minimal/Qwen packets | 14 284 | 12 325 | −13,71%, без потери source rows |

Все числа — локальный o200k подсчёт. В Code Mode часть схем находится в system,
поэтому сокращение только system нельзя выдавать за общую экономию. Не измерены
оплата провайдеру, полная сессия с историей, экономия времени или качество ответа.
Начальный cold baseline не содержал готовый каталог DocAtlas и исключён из
сравнения. Для корректной первой строки сделан один отдельный ready inventory
request с прежними system/permissions/server settings.

## Проверки и обнаруженные дефекты

- **Реальный OpenCode 2.2.5 + свежий installed wheel: PASS.** MCP получил
  project status, source-exact context и прочитал выданный resource URI.
  Files control прочитал разрешённый файл. Запрещённый jobs-запрос не дошёл
  до MCP; внешний файл не доставлен. Вопрос, AGENTS, файлы и SQLite сохранены.
  Только внешний отвечающий provider был scripted: реального inference нет.
- **Публичный CLI/stdin MCP: PASS.** Одна подготовка, шесть context calls,
  три resource reads. Проверены literal source values, исключение private module,
  неизменный patch packet, положительное чтение, отказы changed source и spent
  capability, неизменность базы. Existing continuation integration проверяет
  stale token при смене presentation и совместимость explicit off.
- **Offline replay 16 ранее просмотренных packets: PASS по представлению.**
  Проверены 66 source rows, spans, material/document hashes. Новый Qwen inference,
  minimal dispatch и его runtime admission этим не проверялись: pinned
  multilingual scorer отсутствует, English ONNX не использован как подмена.
- **Installer smoke: PASS.** Guard ошибочно считал U+202F управляющим bidi
  символом. Исправлена граница диапазона; реальные controls и все Cf по-прежнему
  запрещены. Сохранённые model outputs не редактировались.

В настоящем клиенте обнаружилась гонка: MCP connected приходит раньше native
tool definitions. Профиль теперь ждёт фактическое появление context/status
в публичном registry с deadline 10 секунд. В успешной проверке это заняло
819 мс, без дополнительного обращения к модели. Фиксированная стартовая
пауза не используется.

Прежний adapter также ломал typed output native resource/file tools.
Теперь строгий authoritative MCP wrapper отделён от native guard_tools:
у native сохраняются executor, schema и renderer, а проверяется конечный
модельный текст. Согласована строковая output schema строгого wrapper.
Лимит 50 000 и fail-closed проверка MCP content сохранены.

Всего клиентский driver сделал **27 HTTP requests к локальному scripted provider,
0 inference**, включая восемь попыток и ready baseline. Ранний HTTP 500 вызвал
7 физических retries вместо плановых 4 rounds; это явно сохранено в attempts.
Последующие assertion failures завершаются terminal stop. Неуспешные попытки
и исправление ошибочного assertion в первом stdio smoke не удалены.

## Merge и оставшиеся ограничения

Владелец явно поручил merge. Он выполняется обычным PR API с expected head SHA;
успех подтверждается отдельно ответом GitHub и origin/main. Эта запись сама по
себе не является подтверждением уже выполненного merge.

На предшествующей опубликованной вершине 2d667913 было 13 успешных workflows,
8 неуспешных и 1 skipped. В Python 3.12 — 88 падающих тестов. Нельзя называть
их всеми «63 старыми»: часть причин ещё не классифицирована. Тесты не удалены,
quality gold не изменены, общий CI не объявляется зелёным. Текущие целевые PASS
ограничены перечисленными сценариями.

Открытый review P2 про uppercase HTML HREF относится к выключенному и уже
BLOCKED reference-closure v3. Он не включается новым профилем. Исторические
FAIL/BLOCKED и frozen model policies сохранены. Native client errors пока
показываются модели общим недоставленным envelope; точная причина есть в trace.

Эти изменения дают понятный клиентский режим и проверяемый формат источников.
Преимущество перед обычным поиском по конечной полноте ещё не доказано. Это
следующая фаза: связанные условия после scorer и сохранение уже доставленных
условий при составлении ответа; её результаты нельзя приписывать этому smoke.

## Материалы

- [Клиент: результаты и captures](../eval/blind_project_context/step11-client-profile/README_RU.md).
- [Представление: публичные проверки и replay](../eval/blind_project_context/step11-presentation/README_RU.md).
- [Installer и снимок CI](../eval/blind_project_context/step11-ci-readiness/README_RU.md).
- [План и границы второй фазы](../v2plan/STEP11_CLIENT_AND_COMPLETENESS_CHECKPOINT_RU.md).

Wheel SHA256: `73e2bbd73c18a4d20044eb61cc22a0cb78906754bfc4618b79cbf7e70a624070`.
Все 455 packaged Python/source files совпали с текущим деревом; клиентский
профиль сверяется с receipt успешного acceptance-08. Binary wheel не коммитится.

Финальная статическая проверка: module-size PASS, AST 12 новых/изменённых Python
files PASS; source/evidence manifests совпали (9 + 50 + 26 entries). Проверка
whitespace исключает только сохранённый implementation.patch: его семь строк
с единственным пробелом — обязательные context lines unified diff, а не пробелы
в исходном коде. Артефакт и его исходный hash сохраняются. Независимое финальное
ревью adapter/profile/receipts блокирующих замечаний не выявило.

## Подтверждение merge и результат второй фазы

PR #246 успешно смержен в main: `8636d8992ecdfda0abd05738f15d4ddb869a78d1`.
GitHub подтвердил merged=true; origin/main проверен и содержит implementation head.
Результаты исследования пунктов 2 и 5, 13 новых answer-only outputs и ограничения:
[STEP11 completeness](../eval/blind_project_context/step11-completeness/README_RU.md).
