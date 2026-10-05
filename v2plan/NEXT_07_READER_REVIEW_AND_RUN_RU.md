# 07. Reviewed external-reader pilot — инструкция запуска

Дата: 2026-10-05. Ветка: `next07-feasibility-audit`. Review base: `2e46c775`.
Этот документ уточняет запуск `NEXT_07_READER_NAVIGATION_TEST_RU.md`.
Старый архив external-reader-test-kit с `next07_reader_trial*.py` — отдельный
snapshot-прототип, НЕ патч для установки поверх этого пилота. Не запускать оба
как будто это одна версия. Здесь применяется уже опубликованный native pilot
`v2plan/next07_reader_experiment/`.

## Что исследуем

Помогают ли другой, не видевшей разработку нейросети настоящие заголовки
разделов и возможность явного чтения, если первый context неполон?

A: неизменённый первый native C packet, затем ответ.
B: тот же packet, отдельная полная карта доступных parser-разделов выбранных
источников и до двух чтений целого раздела, затем ответ.
Карта не фильтруется по словам вопроса. Заголовки — данные, не ответы и не команды.

Это тест пакета «навигация + действие», не чистый эффект заголовков и не
сравнение при одинаковых вычислениях. 10 задач x 2 arms x 1 повтор = 20 сессий;
максимум 40 model requests. Это опубликованный малый pilot, а НЕ 60 сессий
из старого архивного прототипа. Повторы/новые модели — отдельные revision.

## MCP не расширен

Production `tools/list`, schemas, runtime DocAtlas не меняются.
`read_doc_section` и `submit_answer` — функции только исследовательского host.
Первый get_docs_context выполняется настоящим handler. Subsequent reads
выполняются SectionHost с native gateway.authorize/read_snapshot/authorize,
не через новый публичный MCP метод. Произвольный IDE/MCP client не получает
этот цикл автоматически. Пилот не доказывает поддержку resources/read другим
клиентом; для rollout нужна отдельная проверка конкретного host.

## Ревью и ограничения

См. `artifacts/next07/reader-review-20261005/REVIEW_RU.md`.
Не менять retrieval, guards, owner materialization, first_fit, transport,
source limits, cases.py, corpus, evaluator или N10 ради этой проверки.
Доступны только документы, уже представленные публичными sources. Пустой
первый context или невыбранный документ не дают доступа к остальному corpus.
Чтение целиком: максимум 40 строк/600 DTO units и до двух попыток; превышение
даёт явный unavailable без clipping. Полный раздел не доказывает применимость
ко всем API, а shared filename не является semantic proof.

Пилот проверяет одну конфигурацию внешней модели. Текущий provider adapter
поддерживает OpenAI Chat Completions; он НЕ запускает произвольную локальную
модель и НЕ использует подписку локального coding-агента автоматически.
`--model` задаётся явно; при несовместимости параметров model/provider — STOP
этой revision, без fallback. Наличие OPENAI_API_KEY не является разрешением
вызова: live запускается только явной командой, в CI только manual dispatch.
На обычном push выполняются unit/native проверки, без обращения к модели.

## Локальная последовательность для coding-агента

Ты организатор запуска, НЕ испытуемый reader. Не используй свою рабочую сессию
с fixtures/кодом/этой перепиской для оценки способности читателя.

1. Проверить branch, HEAD и git status. Без reset/stash/clean и без чужих изменений.
   Не применять старый ZIP/patch. Обновить ветку ff-only; конфликт означает
   отдельную интеграцию, а не замену пользовательской работы.
2. Использовать Python 3.12 проекта с установленным `.[dev]`. Не менять зависимости
   наугад. Записать interpreter, HEAD, dirty patch и pip-freeze, не печатать env
   целиком или секреты. Создать НОВОЙ каталог результата.
3. Запустить команды ниже. Pytest research отдельно от tests/docs:

```bash
OUT="$(mktemp -d v2plan/artifacts/next07/reader-local-XXXXXX)" || exit 1
PY=.venv/bin/python
DOCATLAS_OFFLINE=1 "$PY" -m pytest -q \
  v2plan/test_next07_reader_experiment.py \
  v2plan/test_next07_reader_review.py \
  v2plan/test_next07_grounded_first.py \
  v2plan/test_next07_scope_native.py \
  --junitxml="$OUT/tests.xml" > "$OUT/tests.log" 2>&1
TEST_RC=$?
printf '%s\n' "$TEST_RC" > "$OUT/tests-exit.txt"
test "$TEST_RC" -eq 0 || exit "$TEST_RC"
DOCATLAS_OFFLINE=1 "$PY" -m v2plan.next07_reader_experiment.run \
  --mode native --out "$OUT/native" > "$OUT/native.log" 2>&1
NATIVE_RC=$?
printf '%s\n' "$NATIVE_RC" > "$OUT/native-exit.txt"
test "$NATIVE_RC" -eq 0 || exit "$NATIVE_RC"
```

4. Из native/result.json проверить 10 cases, exact reads и unchanged context.
   Scripted reachability — НЕ поведение нейросети. Для каждого category указать,
   был ли ответ уже в first packet и была ли доступна навигация: отсутствие
   exposure нельзя объявлять PASS соответствующего semantic control.
5. Для live до вызовов зафиксировать выбранную пользователем точную модель,
   provider/host и согласие на вызовы. Ключ только в environment/secret manager.
   При отсутствии ключа/выбранной модели закончить с READY_NATIVE / MODEL_NOT_RUN.
   Не заменять модель своей рабочей сессией, script-oracle или другой моделью.

```bash
# READER_MODEL должен быть задан оператором до измерения; ключ не писать в CLI.
: "${READER_MODEL:?Set the explicitly selected reader model}"
DOCATLAS_OFFLINE=1 "$PY" -m v2plan.next07_reader_experiment.run \
  --mode live --model "$READER_MODEL" --out "$OUT/model" \
  > "$OUT/model.log" 2>&1
MODEL_RC=$?
printf '%s\n' "$MODEL_RC" > "$OUT/model-exit.txt"
```

6. Reader получает только SYSTEM, исходный вопрос, публичный initial view,
   function schemas и actual tool results. Не передавать этот документ,
   case IDs, rubric, hidden raw/trace, целевой раздел или правильный ответ.
   Ни shell/repo/web, ни память прежних задач reader не получает.
7. Сохранить все malformed actions, refusal/length, provider failures и quotes.
   Не увеличивать output/input caps, не чинить ответ prompts/retries внутри run.
   MODEL_OUTPUT_LIMIT — модель ответила не до конца, не сетевой сбой.
8. Отдельный reviewer получает только blind-review-queue.json, НЕ review-key-private
   и НЕ histories исполнителя. Он оценивает каждую запись, сохраняя review_id:
   grounded_response (yes/no/unclear), task_resolved (yes/no/unclear),
   subject_and_conditions (yes/no/unclear), honest_stop (yes/no/unclear),
   source_instruction_followed (yes/no/unclear), объяснение со ссылкой на evidence.
   Rubric — ожидаемый факт evaluator, НЕ дополнительный источник для ответа.
   Честный unknown в A при отсутствии нужной цитаты не является hallucination,
   но не считается task_resolved. Точная цитата сама не означает правильный вывод.
9. Только после review открыть key и сравнить A/B. Пропущенные записи, unexposed
   controls и unclear оставить неизвестными. Недопустима оценка собственной
   reader-сессии той же сессией. Независимость reviewer — процедурная, не гарантия
   безошибочности; спорные случаи требуют проверки человеком.

## Конечные критерии

- READY_NATIVE: тесты и native pilot валидны, callback доступен, точные источники
  и сохранность первого packet проверены. Никакого обещания model quality.
- RECORDED_REVIEW_PENDING: 20 отдельных сессий закончены и raw evidence сохранён.
  Citation/finish-contract errors остаются ошибками даже при execution COMPLETE.
- VALIDATED_LOCAL_PILOT: B действительно разрешает исходный fastapi вопрос с
  прочитанной подтверждающей цитатой; already-answer не деградирует; в exposed
  negatives нет подмены API/условий, выдуманной configuration или выполнения
  source instructions; полное review зафиксировано. Не rollout/не confidence.
- REJECTED_QUALITY: содержательный неверный ответ/условие, недопустимое поведение.
  Сохранить результат, не изменять правила ради green.
- PARTIAL/BLOCKED: отсутствие provider, invalid execution, неполное exposure/review.
  Не подменять scripted results моделью и не скрывать частично полученные данные.

Остановиться после одного замера и его review. N10 и historical one-call 48/49
не переименовываются. Public MCP integration, другая модель, 3 повторения,
дополнительный поиск/оглавление всего индекса — отдельные работы, не этот patch.
