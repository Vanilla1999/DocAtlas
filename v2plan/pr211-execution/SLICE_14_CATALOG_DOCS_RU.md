# PR211: текущий каталог и документационные примеры

Следующий узкий slice исправляет пять новых catalog/docs regressions 2199002 и одно прежнее ожидание неактивных документов. Каталог остаётся прежними 14 явно выбранными документами: 12 project и 2 module в docmancer/docs. Исходные V2 25 вопросов, 41 obligation, witnesses, crosswalk и отрицательные controls не меняются.

Тесты независимо фиксируют точные path/role/scope, сохраняют consent/hash/no-discovery, transaction, rollback и source guards. В их fixture создаётся только явно объявленный module directory. Имена двух inventory tests обновлены по смыслу вместе с diagnostic node hashes; прочие transaction test bodies не меняются.

В поддерживаемом workflow добавлен актуальный multiline get_docs_context пример с scope=module и module_path=packages/auth, объявленным в его исходном каталоге. Проверка извлекает обе формы вызова и проверяет фактические аргументы. Документация question planning/evidence selection теперь описывает действующий literal request contract, отдельно explicit lookup, отсутствие заимствованного original credit и answer/edit authority.

V2 lock меняет только hashes двух изменённых активных документов и acceptance pointer; question-planning остаётся вне каталога. Независимый review agent_fixtures_impl APPROVE после исправления отсутствующего module directory. Root проверил diff. AST/compile без исполнения, все active doc hashes, node inventory и whitespace PASS. Новые core/V2 outcomes ещё требуются из обычного PR CI.
