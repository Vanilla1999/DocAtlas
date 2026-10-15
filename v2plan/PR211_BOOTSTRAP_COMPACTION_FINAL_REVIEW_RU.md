# PR #211: final independent review bootstrap compaction

Дата: 2026-10-08. База `3be9c34afa49dcf4278d2910ec29ed37c305225c`.
Решение: **APPROVE** только для финальных файлов ниже. Reviewer независимо
проверил final diff, source producers, существующие tests и фактический JUnit;
решение не унаследовано от автора или reviewer предложенного текста.

| Файл | SHA256 |
|---|---|
| docmancer/templates/agent_contract.md | dccf35d1f256d76b6cc08d6b8913a586ae4ff5c1abff3bd818520974162c5ae2 |
| SKILL.md | 3ad0fa98a913069c715ead5043f4a3c41c70c3befc34774ca01012ea529d12b0 |
| v2plan/PR211_BOOTSTRAP_COMPACTION_REVIEW_RU.md | ba8328e0c6458a60ae9c6ee3e0bdea326bb961900d52c5885f83240549bc77e1 |

## Смысл и границы

Построчно проверены все пять правил. Сохранены первый get_docs_context для
documentation/coding до editing, project/library binding, отсутствие
предварительного skill/guide read, исходный unchanged question и отдельные
calls для независимых вопросов. Same-question lookup остаётся explicit-only,
максимум пять; identities/versions/conditions/negation/comparison sides и запрет
выдуманных translations/rewrites/subquestions/answers/source names сохранены.
Lookup coverage не переносится на original question.

Scope нельзя вывести или расширить из question wording. Project остаётся
repository-level, module_path задаёт module, all остаётся внутри repository
без module filters. Current dependency version не pin-ится без exact/historical
запроса; lockfile changes требуют повторного запроса.

Prepare требует returned recommended_next_action либо explicit lifecycle
request, а также required confirmation/network consent. Status ограничен
explicit status, returned actions/job_id и не служит discovery. Повторяется
тот же запрос только после success, не после failure/cancellation. Сохранены
citation/source identity/hash/span/freshness/provenance, untrusted-document
boundary, отсутствие certification полноты/semantic proof/edit readiness,
отдельные explicit target/authorization и остановка editing при hard_stop.
Отсутствующий hard_stop не предоставляет разрешения.

Изменение `Start documentation/coding with` на `Start documentation/coding:`
оставляет тот же первый tool call и before-editing условие. Заголовок `Guides`
не делает guides обязательными: прямой no-preread clause и `Guides are not
loaded automatically` сохранены. Все четыре назначения ссылок и их пояснения
остались прежними. Advanced patch находится вне default three-tool surface и
по-прежнему требует explicit server startup `DOCATLAS_MCP_ADVANCED_TOOLS=1`.
Ни один обязательный guard не перенесён в optional guide.

## Найденные до публикации regressions устранены

Первый переданный этому reviewer candidate SHA `5178563794a7e97d3f7e9fd14ba1667cf2afa3dd72edd8dd812e997bfcf5d7b6`
сохранял смысл, но нарушал ещё семь существующих PASS nodes:
шесть parameters `tests/docs/test_host_scope_contract.py::test_generated_host_guides_include_the_scope_decision`
и `tests/test_dictionary_exit_delivered_surfaces.py::test_root_guide_is_literal_not_topic_scope_or_proof_policy`.
Они требуют прежние clauses `Never infer or widen scope from question wording`
и `never for discovery`. Статусы всех семи непосредственно проверены в core
JUnit CI 37824782946. Финальные canonical и root восстановили обе clauses;
tests для обхода findings не изменялись.

Ранний `PR211_BOOTSTRAP_COMPACTION_INDEPENDENT_REVIEW_RU.md` с решением CHANGES
REQUIRED относится к другому, ещё более раннему diff и остаётся историческим.
В final также отдельно подтверждены прежние question-planning clauses,
scope regex, recovery/version literals и root/canonical parity, которые
проверял тот review. По ним статически предсказанных PASS regressions не осталось.

Независимый AST scan 527 Python test files проверил string literals длиной
12..500 символов, присутствовавшие в base canonical/root, в исходном регистре
и casefold. 5976 matching checks, отсутствующих в final — 0. Это дополнительная
проверка сохранения существующих literals, а не доказательство полного runtime
PASS или замена смыслового review.

## Размер, links, rendering и identity

Canonical: 261 → 243 whitespace words, 2303 → 2230 UTF-8 bytes.
Managed block с неизменёнными markers: 267 → 249 words. Восемь фактических
installer FAIL на базе проверены по JUnit: они остановились на `267 < 250`.
Прежний порог <250 не повышен. Это word/byte measurement, не фактические model
tokens и не утверждение экономии у клиента.

Root workflow tail начиная с `1. Start` точно совпадает с canonical после
прежней нормализации reference link prefix. Root frontmatter/identity preamble
и canonical schema/identity placeholder preamble сохранены. Четыре root links
ведут к существующим assets, а их bytes, six wrapper templates, marker producer
и installer/rendering code не изменены.

Прочитан `_get_template_content`: canonical встраивается в прежний placeholder,
identity заменяется одним token. Прочитан `public_agent_contract`: identity
производится из machine workflow/examples/runtime ToolSpec hashes, не из prose
bytes. Этот producer и машинная политика неизменны; искусственный новый hash
контракта не требуется. Actual installed files, wheel/desktop packaging и
rendered identity всё равно должны проверяться обычным CI.

Scoped `git diff --check`, статические measurements, AST/literal inventory и
link/parity checks — PASS. Repo imports, tests, installer/build/runtime,
provider/client runs и dependency installations не запускались. Approval
разрешает включить конкретный diff в следующий общий CI; merge-readiness и
actual installed/client acceptance здесь не объявляются.
