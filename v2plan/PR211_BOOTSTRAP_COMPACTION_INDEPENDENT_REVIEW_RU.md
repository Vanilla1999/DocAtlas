# PR211: независимый review сокращения bootstrap

Дата: 2026-10-08. Base: `3be9c34afa49dcf4278d2910ec29ed37c305225c`.
Проверенный исходный diff: `docmancer/templates/agent_contract.md`, SHA-256
`e1f440bb4ab99a985713ee5459f827e9b8d20a9b2d39b8cdb0be82bbd6f23a29`,
и авторский `PR211_BOOTSTRAP_COMPACTION_REVIEW_RU.md`.

**Вердикт для этой версии: CHANGES REQUIRED.** Смысл основных правил сохранён,
но статически установлены нарушения существующих assertions шести nodes,
которые действительно были PASS в core CI на `3be9c34`. Сокращение нельзя
публиковать как исправление installer без устранения этих regressions.
Это review исходного diff; последующий предложенный текст требует отдельного
review после применения владельцем.

## Основание и найденные regressions

Использован настоящий JUnit `pytest-core-3.12-37824782946-1`, artifact
`11571391371`, ZIP SHA-256
`5a432090f914db6ca88a2bc2eaf74ce4dd25ffd0d76a1e8fc38fa8daea9756a9`.
Восемь installer cases падают на `267 < 250`: GitHub Copilot project case
и семь параметров `test_project_install_writes_compact_docs_mcp_bootstrap`.
Причина и сохранение прежнего порога в авторском отчёте указаны верно.

Ниже — предсказанные статическим чтением regressions, а не новый pytest run:

| Прежний PASS node | Нарушение проверенной версии |
|---|---|
| `tests/test_compact_installed_skill.py::test_root_workflow_matches_generated_contract_and_links_to_real_assets` | `SKILL.md` сохранил старый хвост, тогда как тест требует точное равенство canonical начиная с `1. Start` после нормализации link prefixes. |
| `tests/docs/test_host_scope_planning_contract.py::test_public_tool_and_agent_template_explain_scope_without_hidden_widening` | Regex принимает `from question wording` либо `from prose`; новая строка `from wording` не соответствует. |
| `tests/docs/test_agent_recovery_version_guidance.py::test_installed_guidance_preserves_question_conditions_and_current_binding` | Исчезли прежние literals ``omit `version` `` в нижнем регистре и `only after success, not failure`. |
| `tests/docs/test_agent_question_planning_contract.py::test_installed_agent_contract_repeats_question_grouping_rule` | Общий helper требует прежние полные clauses про отсутствие переноса lookup coverage и отсутствие обязательного предварительного чтения skill/guide. |
| `tests/docs/test_agent_question_planning_contract.py::test_rendered_agent_contract_teaches_bounded_semantic_decomposition_without_rewrite` | Тот же helper проверяет canonical и rendered surfaces; новые сокращения его не проходят. |
| `tests/docs/test_agent_question_planning_contract.py::test_agent_surfaces_repeat_gap_directed_follow_up_rule` | Помимо общего helper, тест требует `Guides are not loaded automatically`; замена на `No automatic guide loading` нарушает assertion. |

Все шесть прежних статусов непосредственно сверены с JUnit. Существующие шесть
FAIL параметров `test_installed_templates_render_literal_policy_and_current_identity`
ожидают другую эквивалентную фразу `A lookup does not establish coverage`.
Их исправление не оправдывает regressions прежних PASS. По решению владельца
эти старые failures не входят в данный узкий installer slice; tests и gates
не редактируются.

## Семантическая проверка

Построчно сопоставлены все пять правил с base. Сохранены обычный первый
`get_docs_context` для documentation/coding, неизменный original question и
раздельные calls для независимых вопросов; явные same-question lookups, максимум
пять, сохранение identifiers/versions/conditions/negation/comparison sides и
запрет выдуманных rewrites, answers или source names. Scope остаётся явным:
project repository-level, module_path означает module, all ограничен repository
и не принимает module filters. Current dependency version не pin-ится без
exact/historical запроса; lockfile change требует нового запроса.

Returned action либо explicit lifecycle request по-прежнему необходимы для
prepare; confirmation и network consent не превращены в самостоятельное
разрешение. Status разрешён для explicit status/actions/job_id, не discovery;
retry остаётся неизменным и только после success. Сохранены evidence citation,
source identity/hash/span/freshness/provenance, untrusted-document boundary,
отсутствие completeness/proof/edit certification, отдельные mutation target и
authorization, остановка editing при hard_stop и отсутствие разрешения из
отсутствующего hard_stop.

Четыре reference destinations сохранены. Advanced patch остаётся вне default
three-tool surface, требует explicit server startup setting
`DOCATLAS_MCP_ADVANCED_TOOLS=1`. Ни обязательный guard, ни consent requirement
не перенесён в optional guide. Открытые findings выше относятся к согласованности
реально проверяемых surfaces, а не к разрешению ослабить эти правила.

## Rendering и contract identity

`_get_template_content` в `docmancer/cli/_commands_part01.py` подставляет
canonical текст в `{{CANONICAL_AGENT_CONTRACT}}`, затем заменяет identity
placeholder одним token из `public_agent_contract_identity()`. Identity producer
хеширует machine workflow/examples/runtime ToolSpec records, а не prose bytes;
его реализация не меняется. Template edit сам по себе не требует выдуманного
нового machine identity. Существующая точная подстановка должна проверяться
следующим CI, как и wheel/desktop archive и installed reference files.

Статически подтверждён подсчёт первоначальной версии: canonical 261→243
whitespace words, managed block 267→249, UTF-8 2303→2230 bytes. Markers добавляют
шесть whitespace words; replacement identity token не меняет word count.
Это не model-token measurement и не результат работы installer.

## Переданное владельцу предложение

По запросу владельца подготовлен только scratch candidate
`pr211-acceptance-artifacts/bootstrap-compaction-proposed.md`, SHA-256
`5178563794a7e97d3f7e9fd14ba1667cf2afa3dd72edd8dd812e997bfcf5d7b6`.
Он сохраняет прежние asserted clauses и естественные пояснения ссылок, содержит
243 canonical / 249 managed words и 2228 UTF-8 bytes. Для него stdlib AST извлёк
все прежние clauses `_assert_installed_question_guidance`; все найдены после
той же нормализации. Scope regex, recovery literals и guide-loading clause
также проверены статически; все четыре link targets прежние. Новая `A lookup`
фраза не добавлена, поэтому устранение шести старых corpus-policy failures
не заявляется.

Candidate ещё не является одобрением собственного предложения. Root должен
применить текст, синхронизировать `SKILL.md` с прежней нормализацией links и
передать итоговый diff другому reviewer. Изменений tests, thresholds, roster,
installer, production retrieval/admission или identity code данный review
не вносит.

Никакие repo modules не импортировались, pytest/installer/build/runtime не
запускались, зависимости не устанавливались. Следующий общий CI на точном
опубликованном SHA обязателен; actual installed/client acceptance не заявляется.
