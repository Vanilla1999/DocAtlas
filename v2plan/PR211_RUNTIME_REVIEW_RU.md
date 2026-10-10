# PR #211: independent review runtime harness и CI evidence

Дата: 2026-10-08. Reviewer: координатор; implementation выполняли отдельные agents.
База runtime/CI diff: `21fe472d983f394130849d6fd4e582043d58e9ba`.

## Вердикт

APPROVE narrow harness/evidence delta по static review. Это не утверждение о
прохождении source/installed stdio или CI: runtime проверяется отдельно на
опубликованном SHA. Production retrieval, fixtures, исходные вопросы, gold,
thresholds и required gates в этом slice не меняются.

## Что проверено

- Default inventory остаётся ровно из трёх tools. Default `context_format`,
  включая null, должен отвергаться по advertised schema. Advanced inventory
  включает прежние шесть advanced tools и явно включается отдельным server env.
- Cold default и advanced выполняются отдельными sessions; cold reads не создают
  member storage. Подтверждённая preparation и repeat/CAS выполняются в default.
  После успешного default docs positive проверяется весь rejection matrix.
- Прежняя полная patch matrix запускается в advanced. Source/hash/span/version/
  scope, partial, >32KiB и unchanged generation assertions сохранены. Результаты
  имеют `surface_mode`; advanced docs-default observation не выдаётся за default
  catalog session.
- Общий JSON decoder остаётся строгим. Новый специальный rejection validator
  принимает только точный SDK schema-error text либо typed validation_error с
  phase=validation/tool=get_docs_context без sources и answer/edit grants.
  Handler exceptions, permission errors и произвольный текст не считаются PASS.
- Прежний source-stdio node проверяет actual source origin и обе server modes,
  positive prepared source evidence и отсутствие записи при reads. Имена base
  nodes и parameter roster сохранены; normal conftest не обходится.
- Installed origin checks, console-script prefix, clean env, отсутствие inherited
  credentials/config/PYTHONPATH, private fixture ownership и storage guards не
  ослаблены. Этот slice не создаёт allowlist для любых descendant processes.
- CI pytest selectors/markers, matrix, timeout, dependencies, downstream order и
  failure exit остаются прежними. Добавлены только JUnit destinations и uploads
  XML по существующему pinned action. `if: always()` сохраняет evidence после
  failure; missing XML=warn не делает failed test step успешным.

## Проверки reviewer

`git diff --check`: PASS. `python scripts/check_python_module_size.py`: PASS,
все Python modules в существующем лимите 1000 строк.

Из AST исполнены только три stdlib-only decoder helpers, без imports repository
runtime: 4 корректных structured/text cases приняты, 8 authority/phase/reason/source
corruptions отвергнуты. Это isolated helper check, не normal pytest или MCP transport.

Локально pytest/MCP dependencies отсутствуют; dependency/model downloads не
выполнялись. Полные runtime pytest, настоящий source/installed сервер и реальные
Claude Code/Codex/OpenCode apps этим review не сертифицированы. Их executable
entrypoints в PATH текущего окружения не обнаружены.

## Зафиксированный diff

| Файл | SHA256 |
| --- | --- |
| `scripts/docs_mcp_stdio_smoke.py` | `0dc7e73483b3d11f8e4fb1a6390e3807fc92facd9818fd41150f8a9dffed1b92` |
| `tests/test_docs_mcp_stdio_delivery.py` | `f3dd819b05afe3fc8b5ce29673721d88c5da8beddc2c92f8c9474c0d922d4c16` |
| `.github/workflows/ci.yml` | `499d9595af1d9348f238eed233c54042aa32f27b7ba346620a66ca65545a4b40` |
