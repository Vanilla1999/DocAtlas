# Step 10 file-current baseline: infrastructure-invalid

**All 16 sessions fail to answer: 0/46 required facts, 0/46 supporting fact citations.**
Every attempted file operation was denied with `Permission denied: external_directory`; no source retrieval executed. Final answers explicitly abstain. Exit 0 and session `succeeded` do not establish answer quality.

Do not use these short failure trajectories as a working baseline or claim token savings against them. Usage below is real incurred usage, reconciled between step events and session totals. No production/policy tuning was performed; only frozen dev labels and witnesses were inspected.

## Actual usage

```json
{
  "sessions": 16,
  "fact_pass": 0,
  "fact_total": 46,
  "fact_citations_pass": 0,
  "answers_pass": 0,
  "sessions_without_retrieval": 16,
  "comparison_valid": false,
  "failure": "All file operations denied by external_directory permission before execution.",
  "usage": {
    "input": 44147,
    "output": 2215,
    "reasoning": 38,
    "cache_read": 0,
    "cache_write": 0,
    "input_with_cache": 44147,
    "steps": 46,
    "tool_calls": 30,
    "tool_errors": 30,
    "successful_tool_calls": 0,
    "executed_file_operations": 0,
    "retrieved_source_bytes": 0
  },
  "tool_counts": {
    "glob": 7,
    "read": 12,
    "grep": 11
  },
  "seconds_sum": 155.31
}
```

Output and reasoning are separate provider-reported fields; input-with-cache adds input and cache-read. Tool counts are attempts, not successful reads. No additional model or retrieval calls were made for this evaluation.

| Corpus/case | Facts | Input | Cache read | Output | Reasoning | Tool errors/attempts |
|---|---:|---:|---:|---:|---:|---:|
| L0/T01-en | 0/3 | 2865 | 0 | 127 | 0 | 2/2 |
| L0/T01-ru | 0/3 | 2874 | 0 | 141 | 0 | 2/2 |
| L0/T02-ru | 0/3 | 2869 | 0 | 164 | 0 | 2/2 |
| L0/T05-ru | 0/2 | 2931 | 0 | 123 | 0 | 2/2 |
| L0/T10-ru | 0/3 | 2917 | 0 | 141 | 0 | 2/2 |
| L0/T12-ru | 0/3 | 2878 | 0 | 169 | 0 | 2/2 |
| L0/T15-en | 0/2 | 2888 | 0 | 137 | 0 | 2/2 |
| L0/T19-ru | 0/4 | 2875 | 0 | 138 | 0 | 2/2 |
| L2/T01-en | 0/3 | 2865 | 0 | 114 | 0 | 2/2 |
| L2/T01-ru | 0/3 | 2874 | 0 | 139 | 0 | 2/2 |
| L2/T02-ru | 0/3 | 2881 | 0 | 165 | 0 | 2/2 |
| L2/T05-ru | 0/2 | 1881 | 0 | 120 | 13 | 1/1 |
| L2/T10-ru | 0/3 | 2944 | 0 | 134 | 16 | 2/2 |
| L2/T12-ru | 0/3 | 2869 | 0 | 166 | 0 | 2/2 |
| L2/T15-en | 0/2 | 2888 | 0 | 130 | 0 | 2/2 |
| L2/T19-ru | 0/4 | 1848 | 0 | 107 | 9 | 1/1 |

## L0/T01-en

What is expected of me when I submit a pull request to DocAtlas?

### Actual final answer

I can’t determine DocAtlas’s pull-request expectations because the designated project documentation is inaccessible in this session. I don’t have a source I can cite.

Please provide the project’s contributing guide or pull-request template, and I can summarize the requirements.

### Independent fact and citation grades

- **T01.F1: FAIL; citation FAIL.** Does not give either required branch-name pattern feat/<topic> or fix/<description>; requesting a contributing guide is not the branch convention. Source witness: `CONTRIBUTING.md:61-61`. No supporting citation was supplied.
- **T01.F2: FAIL; citation FAIL.** Does not state that the full test suite must run before opening a PR. Source witness: `CONTRIBUTING.md:62-62`. No supporting citation was supplied.
- **T01.F3: FAIL; citation FAIL.** Does not state that new connectors/fetchers should include tests where practical. Source witness: `CONTRIBUTING.md:63-63`. No supporting citation was supplied.

Tools: glob → Permission denied: external_directory, read → Permission denied: external_directory. No tool returned source text.

## L0/T01-ru

Что от меня ожидается, когда я отправляю pull request в DocAtlas?

### Actual final answer

Не могу определить требования к pull request в DocAtlas: доступ к указанному архиву документации отклонён, поэтому я не могу проверить источники.

Предоставьте, пожалуйста, текст или доступ к документам проекта о внесении изменений — например, `CONTRIBUTING.md` или инструкции для pull request.

### Independent fact and citation grades

- **T01.F1: FAIL; citation FAIL.** Does not give either required branch-name pattern feat/<topic> or fix/<description>; requesting a contributing guide is not the branch convention. Source witness: `CONTRIBUTING.md:61-61`. No supporting citation was supplied.
- **T01.F2: FAIL; citation FAIL.** Does not state that the full test suite must run before opening a PR. Source witness: `CONTRIBUTING.md:62-62`. No supporting citation was supplied.
- **T01.F3: FAIL; citation FAIL.** Does not state that new connectors/fetchers should include tests where practical. Source witness: `CONTRIBUTING.md:63-63`. No supporting citation was supplied.

Tools: glob → Permission denied: external_directory, read → Permission denied: external_directory. No tool returned source text.

## L0/T02-ru

Как безопасно очистить индекс DocAtlas, не удалив данные, которые ещё нужны?

### Actual final answer

Не могу надёжно описать процедуру: доступ к документации DocAtlas в предоставленном корпусе отклонён, поэтому я не смог проверить команды и условия удаления.

До проверки документации **не запускайте очистку индекса**: без неё нельзя установить, какие данные будут удалены и можно ли их восстановить. Предоставьте доступ к корпусу или текст соответствующей инструкции — тогда я помогу разобрать безопасные шаги.

### Independent fact and citation grades

- **T02.F1: FAIL; citation FAIL.** Generic advice to avoid cleanup does not identify doc-atlas clear-index or its bounded preview plan. Source witness: `README.md:192-192`. No supporting citation was supplied.
- **T02.F2: FAIL; citation FAIL.** Does not describe the all-local-index cleanup scope or preservation of configuration. Source witness: `README.md:195-195`. No supporting citation was supplied.
- **T02.F3: FAIL; citation FAIL.** Does not explain that the approved cleanup can be bound to plan_digest. Source witness: `README.md:196-196`. No supporting citation was supplied.

Tools: glob → Permission denied: external_directory, read → Permission denied: external_directory. No tool returned source text.

## L0/T05-ru

Что проверяет верификация привязанной к проекту интеграции с OpenCode и чего она не доказывает?

### Actual final answer

Не могу достоверно ответить: доступ к указанному корпусу проекта запрещён, поэтому я не смог проверить исходные документы и привести ссылки на них.

### Independent fact and citation grades

- **T05.F1: FAIL; citation FAIL.** Does not identify installed wheel, actual installer, stdio MCP, SQLite and MiniLM as the covered verification boundary. Source witness: `docs/PROJECT_BINDING.md:75-75`. No supporting citation was supplied.
- **T05.F2: FAIL; citation FAIL.** Does not distinguish that verification from autonomous OpenCode/model runs and token benchmarks. Source witness: `docs/PROJECT_BINDING.md:79-79`. No supporting citation was supplied.

Tools: grep → Permission denied: external_directory, read → Permission denied: external_directory. No tool returned source text.

## L0/T10-ru

Какой публичный сценарий предлагается для сравнения запусков с выключенным и включённым логированием?

### Actual final answer

Не удалось прочитать документы указанного корпуса: доступ к каталогу `/tmp/opencode/step8-corpora2/L0-0/project` запрещён. Поэтому я не могу достоверно определить предлагаемый публичный сценарий или привести ссылки на источники.

### Independent fact and citation grades

- **T10.F1: FAIL; citation FAIL.** Does not describe reproducing one original user question through the real public API/CLI/MCP. Source witness: `docs/main-flow-evaluation.md:19-19`. No supporting citation was supplied.
- **T10.F2: FAIL; citation FAIL.** Does not describe log-off and log-on attempts from identical initial states. Source witness: `docs/main-flow-evaluation.md:22-22`. No supporting citation was supplied.
- **T10.F3: FAIL; citation FAIL.** Does not require two independent PASS results plus parity. Source witness: `docs/main-flow-evaluation.md:23-23`. No supporting citation was supplied.

Tools: grep → Permission denied: external_directory, read → Permission denied: external_directory. No tool returned source text.

## L0/T12-ru

Как MCP-сервер документации работает с собственной документацией проекта?

### Actual final answer

Не удалось получить доступ к замороженному корпусу проекта: среда отклонила запрос на чтение каталога. Поэтому я не могу достоверно описать, как MCP-сервер работает с документацией проекта, или привести ссылки на источники.

Предоставьте доступ к `/tmp/opencode/step8-corpora2/L0-0/project` или приложите соответствующие документы.

### Independent fact and citation grades

- **T12.F1: FAIL; citation FAIL.** Does not state that reads neither reconcile an index nor write to the repository. Source witness: `docs/mcp-docs-server.md:84-85`. No supporting citation was supplied.
- **T12.F2: FAIL; citation FAIL.** Does not identify the finite explicit docatlas.project-docs.yaml catalog requirement. Source witness: `docs/mcp-docs-server.md:85-86`. No supporting citation was supplied.
- **T12.F3: FAIL; citation FAIL.** Does not state that prepare_docs sync_project_docs without mutation performs no writes. Source witness: `docs/mcp-docs-server.md:89-90`. No supporting citation was supplied.

Tools: grep → Permission denied: external_directory, glob → Permission denied: external_directory. No tool returned source text.

## L0/T15-en

Why shouldn't OpenCode users simply enable DOCATLAS_MCP_MODEL_VIEW=1?

### Actual final answer

I can’t determine that from the designated project documentation because access to the frozen source corpus was denied. I don’t have evidence to explain the risks or cite the relevant lines.

If you can provide the relevant documentation or make the corpus accessible, I can answer from it.

### Independent fact and citation grades

- **T15.F1: FAIL; citation FAIL.** Does not explain that OpenCode retains structuredContent/content but drops response _meta. Source witness: `docs/opencode-compact-text.md:41-41`. No supporting citation was supplied.
- **T15.F2: FAIL; citation FAIL.** Does not explain loss of the original source-packet and unresolvable response-local short references. Source witness: `docs/opencode-compact-text.md:44-45`. No supporting citation was supplied.

Tools: grep → Permission denied: external_directory, read → Permission denied: external_directory. No tool returned source text.

## L0/T19-ru

Какие команды DocAtlas используются для управления Qdrant?

### Actual final answer

Не удалось получить доступ к замороженному корпусу проекта: запросы на чтение и поиск вернули ошибку `Permission denied: external_directory`. Поэтому я не могу достоверно перечислить команды DocAtlas для управления Qdrant или привести ссылки на документацию.

### Independent fact and citation grades

- **T19.F1: FAIL; citation FAIL.** Does not identify the doc-atlas qdrant group or its DocAtlas-owned local-process scope. Source witness: `wiki/Commands.md:106-106`. No supporting citation was supplied.
- **T19.F2: FAIL; citation FAIL.** Does not identify qdrant up or its pinned-binary download behavior. Source witness: `wiki/Commands.md:110-110`. No supporting citation was supplied.
- **T19.F3: FAIL; citation FAIL.** Does not identify qdrant down or stopping the docmancer-managed process. Source witness: `wiki/Commands.md:111-111`. No supporting citation was supplied.
- **T19.F4: FAIL; citation FAIL.** Does not identify qdrant status or its pid/port/url/alive reporting. Source witness: `wiki/Commands.md:112-112`. No supporting citation was supplied.

Tools: grep → Permission denied: external_directory, read → Permission denied: external_directory. No tool returned source text.

## L2/T01-en

What is expected of me when I submit a pull request to DocAtlas?

### Actual final answer

I can’t determine DocAtlas’s pull request expectations because access to the designated project documentation was denied. Please provide the contributing or pull request guidelines, and I can summarize what’s expected.

### Independent fact and citation grades

- **T01.F1: FAIL; citation FAIL.** Does not give either required branch-name pattern feat/<topic> or fix/<description>; requesting a contributing guide is not the branch convention. Source witness: `CONTRIBUTING.md:61-61`. No supporting citation was supplied.
- **T01.F2: FAIL; citation FAIL.** Does not state that the full test suite must run before opening a PR. Source witness: `CONTRIBUTING.md:62-62`. No supporting citation was supplied.
- **T01.F3: FAIL; citation FAIL.** Does not state that new connectors/fetchers should include tests where practical. Source witness: `CONTRIBUTING.md:63-63`. No supporting citation was supplied.

Tools: glob → Permission denied: external_directory, read → Permission denied: external_directory. No tool returned source text.

## L2/T01-ru

Что от меня ожидается, когда я отправляю pull request в DocAtlas?

### Actual final answer

Не могу достоверно ответить: доступ к указанному архиву документации DocAtlas отклонён, поэтому я не смог проверить требования к pull request.

Предоставьте, пожалуйста, текст руководства для участников проекта — например, `CONTRIBUTING.md` или соответствующую страницу документации.

### Independent fact and citation grades

- **T01.F1: FAIL; citation FAIL.** Does not give either required branch-name pattern feat/<topic> or fix/<description>; requesting a contributing guide is not the branch convention. Source witness: `CONTRIBUTING.md:61-61`. No supporting citation was supplied.
- **T01.F2: FAIL; citation FAIL.** Does not state that the full test suite must run before opening a PR. Source witness: `CONTRIBUTING.md:62-62`. No supporting citation was supplied.
- **T01.F3: FAIL; citation FAIL.** Does not state that new connectors/fetchers should include tests where practical. Source witness: `CONTRIBUTING.md:63-63`. No supporting citation was supplied.

Tools: glob → Permission denied: external_directory, read → Permission denied: external_directory. No tool returned source text.

## L2/T02-ru

Как безопасно очистить индекс DocAtlas, не удалив данные, которые ещё нужны?

### Actual final answer

Не могу безопасно рекомендовать процедуру: доступ к документации DocAtlas в предоставленном корпусе отклонён, поэтому я не смог проверить, как очистка индекса влияет на исходные данные.

До проверки документации **не запускайте команды очистки или удаления**. Предоставьте доступ к корпусу или соответствующие страницы документации — тогда я смогу описать проверенные шаги с указанием источников.

### Independent fact and citation grades

- **T02.F1: FAIL; citation FAIL.** Generic advice to avoid cleanup does not identify doc-atlas clear-index or its bounded preview plan. Source witness: `README.md:192-192`. No supporting citation was supplied.
- **T02.F2: FAIL; citation FAIL.** Does not describe the all-local-index cleanup scope or preservation of configuration. Source witness: `README.md:195-195`. No supporting citation was supplied.
- **T02.F3: FAIL; citation FAIL.** Does not explain that the approved cleanup can be bound to plan_digest. Source witness: `README.md:196-196`. No supporting citation was supplied.

Tools: grep → Permission denied: external_directory, read → Permission denied: external_directory. No tool returned source text.

## L2/T05-ru

Что проверяет верификация привязанной к проекту интеграции с OpenCode и чего она не доказывает?

### Actual final answer

Не могу достоверно ответить: доступ к указанному корпусу документации был отклонён, поэтому я не смог проверить источники и привести ссылки на строки. Предоставьте доступ к `/tmp/opencode/step8-corpora2/L2-0/project` или соответствующие документы.

### Independent fact and citation grades

- **T05.F1: FAIL; citation FAIL.** Does not identify installed wheel, actual installer, stdio MCP, SQLite and MiniLM as the covered verification boundary. Source witness: `docs/PROJECT_BINDING.md:75-75`. No supporting citation was supplied.
- **T05.F2: FAIL; citation FAIL.** Does not distinguish that verification from autonomous OpenCode/model runs and token benchmarks. Source witness: `docs/PROJECT_BINDING.md:79-79`. No supporting citation was supplied.

Tools: grep → Permission denied: external_directory. No tool returned source text.

## L2/T10-ru

Какой публичный сценарий предлагается для сравнения запусков с выключенным и включённым логированием?

### Actual final answer

Не удалось определить предлагаемый публичный сценарий: доступ к указанному корпусу документов был отклонён. Поэтому я не могу подтвердить ответ или привести ссылки на источники.

### Independent fact and citation grades

- **T10.F1: FAIL; citation FAIL.** Does not describe reproducing one original user question through the real public API/CLI/MCP. Source witness: `docs/main-flow-evaluation.md:19-19`. No supporting citation was supplied.
- **T10.F2: FAIL; citation FAIL.** Does not describe log-off and log-on attempts from identical initial states. Source witness: `docs/main-flow-evaluation.md:22-22`. No supporting citation was supplied.
- **T10.F3: FAIL; citation FAIL.** Does not require two independent PASS results plus parity. Source witness: `docs/main-flow-evaluation.md:23-23`. No supporting citation was supplied.

Tools: grep → Permission denied: external_directory, glob → Permission denied: external_directory. No tool returned source text.

## L2/T12-ru

Как MCP-сервер документации работает с собственной документацией проекта?

### Actual final answer

Не могу определить это по документам проекта: доступ к указанному замороженному корпусу отклонён средой (`Permission denied: external_directory`). Поэтому у меня нет проверенных источников, на которые можно сослаться.

Предоставьте доступ к `/tmp/opencode/step8-corpora2/L2-0/project` или пришлите соответствующие документы — тогда я смогу ответить со ссылками на строки.

### Independent fact and citation grades

- **T12.F1: FAIL; citation FAIL.** Does not state that reads neither reconcile an index nor write to the repository. Source witness: `docs/mcp-docs-server.md:84-85`. No supporting citation was supplied.
- **T12.F2: FAIL; citation FAIL.** Does not identify the finite explicit docatlas.project-docs.yaml catalog requirement. Source witness: `docs/mcp-docs-server.md:85-86`. No supporting citation was supplied.
- **T12.F3: FAIL; citation FAIL.** Does not state that prepare_docs sync_project_docs without mutation performs no writes. Source witness: `docs/mcp-docs-server.md:89-90`. No supporting citation was supplied.

Tools: grep → Permission denied: external_directory, read → Permission denied: external_directory. No tool returned source text.

## L2/T15-en

Why shouldn't OpenCode users simply enable DOCATLAS_MCP_MODEL_VIEW=1?

### Actual final answer

I can’t determine that from the project documentation: access to the designated frozen corpus was denied. I therefore can’t verify what `DOCATLAS_MCP_MODEL_VIEW=1` does or why OpenCode users should avoid enabling it.

### Independent fact and citation grades

- **T15.F1: FAIL; citation FAIL.** Does not explain that OpenCode retains structuredContent/content but drops response _meta. Source witness: `docs/opencode-compact-text.md:41-41`. No supporting citation was supplied.
- **T15.F2: FAIL; citation FAIL.** Does not explain loss of the original source-packet and unresolvable response-local short references. Source witness: `docs/opencode-compact-text.md:44-45`. No supporting citation was supplied.

Tools: grep → Permission denied: external_directory, read → Permission denied: external_directory. No tool returned source text.

## L2/T19-ru

Какие команды DocAtlas используются для управления Qdrant?

### Actual final answer

Не удалось проверить документацию DocAtlas: доступ к указанному корпусу был отклонён. Поэтому я не могу достоверно перечислить команды управления Qdrant.

Предоставьте доступ к корпусу или пришлите соответствующий фрагмент документации.

### Independent fact and citation grades

- **T19.F1: FAIL; citation FAIL.** Does not identify the doc-atlas qdrant group or its DocAtlas-owned local-process scope. Source witness: `wiki/Commands.md:106-106`. No supporting citation was supplied.
- **T19.F2: FAIL; citation FAIL.** Does not identify qdrant up or its pinned-binary download behavior. Source witness: `wiki/Commands.md:110-110`. No supporting citation was supplied.
- **T19.F3: FAIL; citation FAIL.** Does not identify qdrant down or stopping the docmancer-managed process. Source witness: `wiki/Commands.md:111-111`. No supporting citation was supplied.
- **T19.F4: FAIL; citation FAIL.** Does not identify qdrant status or its pid/port/url/alive reporting. Source witness: `wiki/Commands.md:112-112`. No supporting citation was supplied.

Tools: grep → Permission denied: external_directory. No tool returned source text.

## Portability and limitations

`baseline.json` embeds all final answers, manual per-fact reasons, relevant frozen source witness text/hash/coordinates, exact tool traces, per-step token accounting, session receipts, and hashes of original event/session/stderr files. It is reviewable without the temporary run directory. This artifact grades the observed failed baseline only; a repaired baseline and candidate need separate grading. No retrieval-quality failure is inferred from a permission-denied operation that never executed.
