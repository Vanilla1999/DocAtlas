# Step14 live runner — экспериментальный setup/capture

Новые скрипты находятся только здесь. Старые protocol, manifest, tasks и reports сохранены.
`verify_inputs.py` проверяет прежние hashes: 4 вопроса, 6 документов, 19 scoring positions.
`review-criteria.json`, tasks/facts и старые ответы не включаются в config, corpus или prompt.

## Команды

Из корня данного worktree:

```sh
EVAL=eval/blind_project_context/step14-host-language-live
PY=/home/viadmin/.local/share/docatlas-eval/step14/venv/bin/python
BASE=/home/viadmin/.local/share/docatlas-eval/step14

"$PY" -B -I "$EVAL/verify_inputs.py"

# Новый attempt: никогда не перезаписывать прежний.
"$PY" -B -I "$EVAL/run.py" setup --attempt attempt-02 \
  --python "$PY" --assets "$BASE/assets" \
  --wheel "$BASE/wheel/doc_atlas-1.3.2-py3-none-any.whl" \
  --work "$BASE/work/attempt-02" --state "$BASE/work/attempt-02/state" \
  --opencode /home/viadmin/.opencode/bin/opencode --auth existing-user

# Только родитель запускает после review. Используется существующий аккаунт
# OpenCode/Terra; API key и новый login не нужны.
"$PY" -B -I "$EVAL/run.py" run --attempt attempt-02

# Анализ завершённого или частичного прогона; выходной файл должен быть новым.
"$PY" -B -I "$EVAL/account.py" --attempt attempt-02 \
  --output "$PWD/$EVAL/accounting-attempt-02.json"
```

`attempt-01` setup остановился до public preparation: существующие родители
`$BASE` и `/home/viadmin/.local/share/docatlas-eval` имеют mode `0775`.
Installed policy требует отсутствия group/other-write во всех предках state.
Родитель сообщил об исправлении прав. По его последнему указанию setup пока
не повторялся; runner не менял эти каталоги. Исторический failed attempt сохранён.

Пути python/assets/wheel/work/state/opencode — параметры CLI. Assets, wheel и venv
только читаются; weights/env не копируются. Исторический policy читается из
`step10-qwen-validation/provenance/original-policy.json`; его hash совпадает с
`$BASE/install/policy.json`: `16fb92b9687d68c30cdc8bfa8656b20d512da2b9b8600497ed78a0f5742d0f11`.
Setup сравнивает установленный package с каждым `docmancer/` member wheel,
проверяет assets через установленный verifier и runtime против прежнего pinned.

## Credentials и изоляция

Каждая сессия запускается `opencode run --standalone` в отдельном Location;
новый private server живёт только на время сессии. Общий сервер не используется.
Единственный/default режим — `--auth existing-user`. Сохраняются настоящий
HOME `/home/viadmin` и `XDG_DATA_HOME=/home/viadmin/.local/share`. Установленный
OpenCode использует существующий пользовательский credential store обычным путём;
runner не читает secret values и не копирует/не symlink'ит credential files.
API keys из окружения и `OPENCODE_DB` не передаются. Нового login нет.

Изолированы XDG config/state/cache и TMPDIR внутри `work/attempt-*`.
**Data/credentials, DB сессий и native log общие**, а server/process group — private.
Обычная запись новых session records, native logs и refresh существующего OAuth
может менять общий data store; это не read-only доступ к нему. Shared DB не
копируется, не редактируется напрямую и не удаляется. Глобальные configs не меняются.
Shared data/native logs не включаются в capture и не архивируются runner'ом.
Таким образом, explicit разрешение использовать существующий user data store —
исключение из первоначальной полной изоляции записи; остальных широких writes нет.

Проверено без запуска сервера/provider: `opencode debug paths` в исходном окружении
и с точным `client_environment` runner. Data/DB/log совпали с пользовательскими;
config/state/cache/tmp указывают в новый work. Setup сохраняет `auth-topology.json`,
run повторно сверяет topology до запуска. Текущий OpenCode model catalog подтвердил
активную `openai/gpt-6.1-terra` с вариантом `low`; это не успешный inference smoke.
`AUTH_EXISTING_USER_VERIFICATION.json` фиксирует read-only проверку.

Наследуемые direct/.opencode configs, plugins и AGENTS в предках work запрещены
preflight. Skills из home-предков удаляются runtime transform в observer для всех
трёх arms; исходные common/profile/source инструкции сохраняются.

## Исполнение и stop conditions

Порядок: V-M1..V-M4, внутри каждого A/B/C; всего 12 fresh sessions.
Все: `openai/gpt-6.1-terra#low`, agent `measure`, 12 steps, timeout 900 s.
A: concise-v1/model; B: concise-v1/host-v1; оба pinned Qwen + one-hop-v1.
C: files/concise-v1 с оригинальной files-инструкцией.
Общие experimental controls: explicit title, auto compaction/warming off,
provider retries vetoed, encoding=none для читаемого native capture во всех arms.
Нет продолжения после ошибки/timeout/OOM/scan_incomplete.
Started markers, setup/config/source hashes и новый output запрещают повтор.

Public preparation — один настоящий установленный stdio `prepare_docs`, только
lexical isolated member corpus/index. Consent hashes и storage target получаются
из установленного пакета. Нет canonical retrieval/probe, Qwen loading или provider
в setup. Preparation не является результатом live comparison.

Transport делает exclusive claim **до** запуска CLI, поэтому reconnect не создаёт
вторую копию MCP. Host registry содержит PID/start_ticks/PGID/SID/PID namespace
transport и installed server. `session_runtime.py` переиспользует проверенную
Step13 pidfd/held-leader cleanup; не вызывает pkill/service stop/shared API.
В finally завершается private group и только зарегистрированные MCP identities.
До/после каждой сессии сохраняются `nvidia-smi` compute PIDs и память; surviving
новый compute process или рост >128 MiB прекращает прогон. Исходный ambient
compute (например, уже работающий Blender) фиксируется в baseline и сохраняется;
чужие процессы не трогаются.
Corpus и весь member DB hash сверяются перед/после каждой сессии.

## Capture и границы

* `stdio-events.jsonl`: настоящие JSON-RPC request/полный response с Python
  `monotonic_ns`, до доставки ответа host. Байты протокола не заменяются.
* `capture/events.jsonl`: prompt-admission metadata; assembled context; native
  HTTP request/response bodies, WS frames; model tool hooks; retry decision.
  Headers, URLs и environment не записываются.
* `capture/first-provider-request.json`: первый настоящий pre-dispatch hook,
  включая body. Это не remote receipt/серверный network timestamp.
* `capture/state.json` и `capture.response.completed`: запись полной response
  и фактического usage завершена. Перед owned cleanup launcher ждёт до 10 s
  завершения capture, удерживая unreaped PID. Недостающий usage/capture — failure,
  а не ноль. HTTP hooks могут выбирать HTTP вместо WS по documented V2 policy;
  observer одинаков во всех arms.
* B: accounting требует genuine status response before first request, matching
  binding/audit, `declared/en` hint с тем же prompt_id и исходный вопрос в body.
  Host executor не обязан появляться в generic model tool hooks, поэтому они не
  используются как доказательство отсутствия host call.
* Provider usage deduplicated по response ID; input включает cached, reasoning
  не прибавляется к output. Missing поля — `null`. Цена и local tokenizer estimates
  не вычисляются. Qwen pairs суммируются только из фактического
  `source_selection.model_pairs` каждого MCP response; при отсутствии поля — `null`.
* Raw tool results и последующие request bodies сохранены для независимой проверки
  доставки источников/hash/span. Accounting не выставляет semantic quality PASS:
  ответы и 19 facts необходимо оценить отдельно по исходным данным/review criteria.

Проверки агента: immutable input checker, Python AST, Node syntax, installed
OpenCode debug paths для existing-user topology; setup status
фиксируется в отдельном attempt. Live provider/inference этим агентом не запускались.
Нативный capture-drain/cleanup на настоящей Terra сессии остаётся проверкой родителя.

Источники V2 API: https://opencode.ai/v2/docs/cli (private standalone),
https://opencode.ai/v2/docs/build/plugins/server (native HTTP/WS/retry/tool hooks),
https://opencode.ai/v2/docs/config (XDG config/substitution/compaction),
https://opencode.ai/v2/docs/providers (credentials/encoding/transport).
