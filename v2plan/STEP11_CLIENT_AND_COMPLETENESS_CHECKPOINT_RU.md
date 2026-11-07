# Step 11: клиент, представление контекста и исследование полноты

Дата: 7 ноября 2026, Europe/Moscow.
Исходная проверенная вершина: `2d667913f279ba72104f158ee6500d75d5ace81f`.
PR: https://github.com/Vanilla1999/DocAtlas/pull/246.

## Новое поручение владельца

В этой беседе владелец поручил реализовать пункты 3 и 4 последнего разбора
(лёгкий клиент и literal выдача без видимых source hashes), слить накопленную
ветку в main, затем исследовать и проверить решения пунктов 2 и 5
(потеря связанных условий и потеря уже доставленных фактов в финальном ответе).
Это новое разрешение на scoped implementation, проверки и merge. Исторические
ограничения Step10 описывают прежние эксперименты и не переписываются в PASS.
Словари синонимов, подстановок, aliases и позиционные таблицы расшифровки
в новых решениях не используются. Пункт 1 (tiny-scope production route) сюда
не включён.

## Первая фаза — реализация и merge

- Явный профиль `documentation-light-v1` для чтения подготовленной документации.
  Привязка проекта, исходники, язык, scope/version и необходимые правила среды
  сохраняются. Сравнение с файлами имеет общий текст правил и явные различия tools.
- `DOCATLAS_CONTEXT_PRESENTATION=literal-v2`: ordinary JSON и исходные public
  references, без индексных columns/groups и видимых per-source content_sha256
  в initial docs_context. Canonical packet и машинные проверки не изменяются.
  Историческое представление сохраняется по умолчанию; patch/source reads вне
  нового изменения. Revision участвует в continuation binding и delivery pricing.
- Новые проверки только integration и выше, через реальные API/CLI/MCP.
  Installed wheel, in-process, scripted client и реальная модель учитываются
  раздельно. До commit проверяются module-size и whitespace.
- Исправляется ошибочная классификация U+202F как bidi control в installer guard,
  без изменения сохранённых model outputs и без исключения путей из проверки.
- Общий CI уже имеет красные quality/contract checks. Их не удалять, не менять
  эталоны и не скрывать ради merge. Зафиксировать фактические статусы и границы
  целевых PASS. Merge выполняется штатным PR API с expected head SHA.

## Вторая фаза — после merge

Сначала первичные источники и отдельный замороженный план сравнения. Разделять:
1) найденные кандидаты; 2) выдаваемые исходники; 3) окончательный ответ модели.
Не подменять один уровень другим и не менять старый blind-260 holdout.

Для пункта 2 использовать source-exact replay сохранённых scores/packets,
отдельно сравнить прямые ссылки и полный обход, проверить навигационное раздувание,
отсутствующие связи, scope/anchors и явно незакрытые зависимости.
Никакое значение score само по себе не доказывает отсутствие обязательного условия.

Для пункта 5 фиксировать одинаковые полные исходники и исходные вопросы до ответов,
раздельно оценивать полные/частичные/пропущенные условия, ложные утверждения и отказ
при отсутствии ответа. Инструкция не содержит названий правильных фактов.
Конкретный доступный model/client runtime и bounded budget будут записаны до
вызовов; отсутствие provider credentials нельзя подменять выдуманным Terra run.

## Текущее состояние

Реализация и целевые проверки первой фазы завершены; публикация и merge
выполняются отдельно и до подтверждения GitHub не заявляются.

- Unicode correction: один existing installer smoke PASS, frozen model reports
  побайтно сохранены. Это старый smoke с заглушками внешних installer commands.
- Literal-v2: public source CLI/stdin MCP проверил 1 prepare, 6 context calls,
  3 resource reads; source bytes/refs/scope сохранены, patch unchanged, source read
  сохраняет hash, changed-source/spent capability отклоняются. Отдельный public
  continuation scenario проверил привязку presentation. Исправление assertion
  trust notice после первого harness FAIL сохранено в evidence.
- Обычный non-minimal packet вырос 555 → 584 local o200k tokens; hashes там
  уже не показывались. Offline replay 16 seen Qwen packets: 14 284 → 12 325,
  66 source records сохранены. Это не новый Qwen/minimal runtime acceptance.
- Minimal scorer требует другой pinned mmarco safetensors/runtime, которого
  здесь нет; имеющийся English MiniLM ONNX не подменяет его. Inference calls 0.
- Собран fresh wheel 1.3.2: SHA256
  `73e2bbd73c18a4d20044eb61cc22a0cb78906754bfc4618b79cbf7e70a624070`;
  все 455 packaged Python/source files сверены с текущим деревом.
- Pinned OpenCode 2.2.5 установлен и проверен по SHA512. Два настоящих
  клиентских сеанса с scripted provider прошли: MCP — четыре запроса,
  isolated files-control — два. Проверены реальные инструменты и отказы,
  исходный вопрос, AGENTS, scope, неизменность файлов и базы. Native resource
  read проверен на реально выданном URI с корректным end_of_source.
- Готовый historical inventory: 2034 system + 348 tools = 2382 local tokens;
  новый MCP: 945 + 1190 = 2135, уменьшение на 247 (10,37%). Files control:
  654 + 597 = 1251. Это один первый запрос, не total usage/cost/quality.
  Cold baseline без готовых DocAtlas tools исключён из сравнения.
- Все восемь попыток и отдельный ready baseline сохранены в ledger:
  27 HTTP requests к scripted provider, 0 inference. Ранний HTTP 500 вызвал
  семь физических retries вместо четырёх плановых rounds; превышение явно
  записано. Исправления driver не скрывают этот неуспешный прогон.
- Хеши product profile/adapter точно совпадают с успешным acceptance-08.
  Неуспешные проверки отнесены к их фактической границе. Native error envelope
  пока общий; причина отказа проверена в host events и stdio dispatch.
- Ключи API и авторизованный Terra/Codex endpoint в среде не обнаружены;
  `codex login status` вернул `Not logged in`. Это ограничение доступного runtime,
  а не запрет пользователя на исследование. Будущие альтернативные модельные
  проверки должны явно указывать фактическую модель и границу сравнения.

Подробности: `eval/blind_project_context/step11-presentation/`,
`eval/blind_project_context/step11-ci-readiness/`,
`eval/blind_project_context/step11-client-profile/` и
`reviews/STEP11_IMPLEMENTATION_RU.md`. Исторический blind holdout не читается.

## Завершение первой фазы и исследование после merge

PR #246 merged=true, main `8636d8992ecdfda0abd05738f15d4ddb869a78d1`.
После merge завершены offline link study и 13 уникальных answer-only генераций
Astra Pro по заранее опубликованным inputs; сохранены независимая оценка и root review.
Локальная среда отключилась после offline study: его недоступные raw artifacts
отмечены отдельно. Новый answer study восстановлен и полностью опубликован через
GitHub; это не воспроизведение Terra Low и не billing measurement.
Отчёт: `eval/blind_project_context/step11-completeness/README_RU.md`.
