# PR211: сокращение установленной стартовой инструкции

Дата: 2026-10-08. Base: `3be9c34afa49dcf4278d2910ec29ed37c305225c`.
Изменены canonical `docmancer/templates/agent_contract.md` и соответствующий
workflow tail корневого `SKILL.md`; root links сохраняют свои repository paths.
В этом slice tests, runtime code, schemas и contract identity producer не меняются.

## Причина

В core CI 37824782946 восемь существующих installer cases завершаются на
`267 < 250`: общий managed bootstrap вырос до 267 слов. Требование короткой
стартовой инструкции сохраняется. Сокращается сам текст, без повышения порога
и без переноса обязательных правил в необязательные reference files.

Canonical template: 261→243 whitespace-delimited words, 2303→2230 UTF-8 bytes.
Managed project block с теми же start/end markers: 267→249 words. Placeholder
contract identity заменяется одним беспробельным hash token, поэтому на этот
подсчёт не влияет. Это статическое измерение шаблона, не фактические model tokens
и не результат выполнения installer.

## Сохранённый смысл

1. Documentation/coding начинают с обычного get_docs_context, project или library;
   предварительный skill/guide read не требуется. Исходный вопрос не меняется,
   независимые вопросы используют отдельные calls.
2. Только явно supplied lookup_queries для того же вопроса, максимум пять;
   identifiers/version/conditions/negation/comparison sides сохраняются. Нельзя
   выдумывать переводы, rewrites, subquestions, answers или source names.
   Прежняя полная формулировка «Lookup coverage does not transfer to the original
   question» и отсутствие переноса coverage сохранены.
3. Scope не выводится и не расширяется из wording. Все project/library/version/path
   bindings и точные значения project/module/all прежние, включая отсутствие module
   filters у all. Current dependencies не pin-ятся без exact/historical запроса;
   lockfile changes требуют повторного запроса.
4. prepare_docs требует returned action либо explicit lifecycle request, confirmation
   и network consent; docs_status ограничен explicit status/actions/job_id.
   Discovery через status запрещён, повтор только после success; failure/cancel
   не разрешают повтор.
5. Citation/source identity/hash/span/freshness/provenance, untrusted-data boundary,
   отсутствие completeness/proof/edit certification, отдельные mutation target и
   authorization и hard_stop semantics сохранены в корневом тексте.

Все четыре reference links и их назначения сохранены. Patch остаётся вне default
three-tool surface, требует explicit server startup setting
`DOCATLAS_MCP_ADVANCED_TOOLS=1`. Guides необязательны и не загружаются автоматически.
Contract schema/identity placeholders и ownership markers не меняются.

## Проверка

Новых tests нет: существующие installer cases проверяют размер и наличие инструментов;
compact-installed-skill и workflow/corpus-policy suites проверяют rendering, identity,
links, сохранение user text, no-follow/write refusal и policy clauses. Их assertions,
roster, thresholds и execution path остаются прежними. Следующий общий CI должен
проверить фактический rendering и installed artifacts на новом SHA.

Source SHA256: `dccf35d1f256d76b6cc08d6b8913a586ae4ff5c1abff3bd818520974162c5ae2`.
Independent review — отдельно. Runtime этого изменения пока NOT RUN.

Предварительный review выявил literal-clause и root/canonical parity regressions
в раннем предложении. Они исправлены до публикации: прежние policy clauses
восстановлены, SKILL tail синхронизирован. Финальный reviewer проверяет новый hash
отдельно от предыдущего CHANGES REQUIRED; ранний diff не публиковался.
