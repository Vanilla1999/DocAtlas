# PR #211: release test и delivered result schemas

Дата: 2026-10-08. Узкая test-only миграция, автор — координатор.

## Подтверждённая причина

Full CI на HEAD `b68759e65f52317928ba22166248e679098024ae`, merge checkout
`964056442f67b0d913310d3f8a295deb3c90263e`: все 38 параметров
`tests/test_release_gate.py::test_stdio_smoke_accepts_structured_content_and_legacy_json_text`
завершаются на последнем documentation assertion. JUnit Python 3.11/3.12/3.13
даёт одинаковые node IDs и outcomes. Все предшествующие self-host controls,
decoder checks и проверки замороженных thresholds в этих nodes достигаются.

Assertion требует слова `docs_answer` в исходном Python-файле
`docmancer/mcp/_docs_server_resources.py`. Короткий resource уже на исходном
21fe472d описывает workflow и границы permission, а не перечисляет все result
variants. Они остаются в реально advertised outputSchema; patch представлен
только в явно включённом advanced режиме. Основание — пункты 4–5
`CURRENT_WAVE_DECISIONS_RU.md`, compact surface и packaged optional guides.

## Изменение и сохранённые guards

Семь maintained user-facing documents по-прежнему обязаны содержать прежние
четыре result kind/status термина. Только чтение internal Python source в этом
списке заменено проверкой фактически delivered MCP contract:

- default kind enum ровно `docs_answer`/`docs_context`, status включает
  `insufficient_evidence`; default не предлагает context_format или oneOf;
- advanced сохраняет ту же docs schema и отдельный typed patch_context branch;
- actual `read_docs_resource` возвращает quickstart с get_docs_context,
  recommended_next_action, hard_stop/permission guards, explicit advanced startup
  и запретом автоматически включать режим или загружать tools чтением guide.

Production/resources и все thresholds, gold cases, 800-token/3-source controls,
negative mutations, decoder assertions и 38 parametrized self-host cases не
меняются. Доказательство corpus relevance, contamination, citation integrity и
true/false authority flags не заменяется доступностью ресурса.

Этот slice не исправляет frozen retrieval gate. Успех required-release на b687
уже подтверждён отдельным workflow; unit test migration не переименовывает его
в green required-ci. Нужны независимый review и joint CI на конечном SHA.
