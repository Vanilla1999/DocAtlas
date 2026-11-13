# Arm D: остановка до Terra

Статус: **BLOCKED_PREPARATION_CONFIG_MISMATCH_STOPPED**, не результат сравнения.
Ни одной Terra-сессии и ни одного provider request не запущено. Semantic grade отсутствует.

База historical A/B/C: `../step14-host-language-live`, commit
`e62fa9e357bd22731cddabe930532a4a2faecc18`. Будущий D является последовательным
историческим сравнением, не одновременным рандомизированным экспериментом.

## Выполнено

- Прочитаны AGENTS.md, skill OpenCode и V2 config/MCP guides.
- Открыты схемы реального Grounded MCP; найден установленный тот же
  `@arabold/docs-mcp-server@3.2.1`, которым пользуется текущий MCP.
- Изучен `eval/grounded_v40/run.py`. Повторён его подход `--config`, но обнаружено,
  что без дополнительных environment overrides он здесь не задаёт store.
- Шесть pinned GitHub raw URL загружены и побайтово сверены с frozen corpus.
  Сохранены `sources.json` и `source-bytes/`. Private/oracle/report не передавались.
- Выполнены шесть реальных CLI scrape: каждый maxPages=1, maxDepth=0,
  followRedirects=false, exact include-pattern, clean=false, одна новая библиотека
  `meridian-step15-e62fa9e3`, версия `1.0.0`. Все receipts — `preparation/`.
- Read-only SQLite inspection подтвердил ровно шесть страниц и девять chunks
  новой библиотеки. Существующая библиотека не удалялась/не переиндексировалась.

## Блокировка

Ожидался store:
`/home/viadmin/.local/share/docatlas-eval/step15/work/attempt-01/grounded-store`.

Фактически новый индекс оказался в:
`/home/viadmin/.local/share/docs-mcp-server/documents.db`.

`effective-config.json` фиксирует: `--config .../grounded.yaml config` возвращает
default storePath, telemetryEnabled=true, embeddingModel=text-embedding-3-small
вместо YAML. Scrape отдельно получал `--telemetry=false`; в сохранённых chunks
embedding отсутствует. Причина игнорирования YAML ещё не установлена.
Предполагаемое исправление — явные `DOCS_MCP_CONFIG` и `DOCS_MCP_APP_STORE_PATH`
как в старом harness либо явный CLI `--store-path`, но оно **не запускалось**.

По заданному правилу «errors preserve stop» после обнаружения несоответствия
выполнена только read-only диагностика. Повторного indexing/started cases нет.
Изолированные Locations и Terra config ещё не созданы, авторизация не читалась.
Это исправимая ошибка подготовки, не доказательство невозможности Grounded.
Новый library в default store оставлен на месте; удаления не выполнялись.

## Extraction boundary

Raw bytes совпадают со всеми шестью frozen documents. Grounded удаляет пустые
строки при сборке chunks: 0/9 chunks — точная непрерывная подстрока исходного
файла. При этом **каждая строка каждого chunk точно присутствует в исходнике**:
`extraction-line-map.json` содержит независимую привязку к номерам исходных строк.
`index-inspection.json` содержит полные chunks, metadata, hashes, content_url.
Indexed URL нормализован без `.md`; content_url сохраняет настоящий pinned `.md`.
Нельзя объявлять hash indexed chunk равным hash исходного файла или выдумывать
непрерывный span после удаления пустых строк.

## Независимая проверка

Из корня isolated checkout:

```sh
cat eval/blind_project_context/step15-grounded-live/status.json
cat eval/blind_project_context/step15-grounded-live/effective-config.json
git status --short
```

`inspect_index.py` документирует read-only запросы к фактическому индексу.
Его выходные файлы создаются эксклюзивно: не перезапускать поверх текущих receipts.
`prepare.py` также не перезапускать: work directory уже существует.

Для продолжения нужен отдельно зафиксированный recovery после этой остановки:
сначала проверить effective configuration и шесть-source isolation нового store,
затем подготовить четыре свежих Location, Grounded-only allowlist profile,
reviewed existing-user auth/wall-v2 observer и только после проверки начать D.
Сохранять original questions; не задавать question→doc mappings. Historical
общий concise/source-to-draft prompt брать из A/B/C, менять лишь backend mechanics.

Commit/push не выполнялись. Основной рабочий checkout не изменялся.
