# PR #211: independent review installed lookup wording

Дата: 2026-10-08. База `3be9c34afa49dcf4278d2910ec29ed37c305225c`.
Решение: **APPROVE** для `tests/test_dictionary_exit_corpus_policy.py`, SHA256
`f768ee34f36af4593fe88eb1b07c4080a88898ebde3f56a7fac2e83a44774ac0`.
Это самостоятельный test-only slice; решение не одобряет bootstrap prose
или фактический installed runtime без их отдельного review/CI.

В фактическом core JUnit CI 37824782946 шесть существующих template cases
остановились на старом неполном prefix `A lookup does not establish coverage`.
Текущий canonical producer содержит полную фразу
`Lookup coverage does not transfer to the original question.`
Machine workflow `retrieval_only_answer.lookup_coverage_transfers_to_original`
равен false, `free_form_lookup.original_question_unchanged` равен true;
политика explicit same-question lookup отделяет поиск от coverage исходного
вопроса. Это обосновывает successor независимо от фактического сообщения FAIL.

Изменён ровно один Assert. Он принимает две полные эквивалентные clauses:

- `A lookup does not establish coverage of the original question.`
- `Lookup coverage does not transfer to the original question.`

Обе сохраняют отрицание, lookup coverage и явную привязку к original question.
Это не поиск отдельных слов или сокращённого prefix. Независимая статическая
проверка строк подтверждает rejection пустого текста, старого незавершённого
prefix, положительного establish/transfer, отсутствующего original-question
target и замены target на another question. Production coverage/admission и
producer wording этот slice не меняет.

AST comparison подтверждает: изменена только
`test_installed_templates_render_literal_policy_and_current_identity`;
все imports, остальные functions, decorators и parameters неизменны.
Остаются ровно шесть parameters: skill.md, claude_code_skill.md,
claude_desktop_skill.md, cursor_agents_md.md, copilot_instructions.md,
project_bootstrap.md. Assert inventory всего модуля 52 → 52: 51 Assert
AST-identical, заменён один. Остальные семь assertions изменённого node
сохраняют current identity, отсутствие unresolved placeholder, явно supplied
lookups, отдельный mutation target/authorization и три запрета старых
inferred-behavior instructions.

Все 11 base test nodes сохранены. Inventory SHA256
`d68011233a9555b3057ad4f67584670a1d6ae6d4815e34862e77532be0390b8e`
совпадает с неизменённым
`tests/diagnostic_labels.dictionary_exit_corpus_policy.json`.
Прочитан `_get_template_content`: все шесть wrappers используют тот же canonical
contract и существующую substitution identity. Producer identity по-прежнему
связан с machine workflow/examples/runtime ToolSpecs; этот механизм не меняется.

`ast.parse`, compile AST без исполнения, inventory и scoped `git diff --check`
— PASS. Repository functions/tests, imports, installer, client/provider runs
и installations локально не запускались. Следующий обычный CI должен проверить
фактические rendered templates на опубликованном SHA; шесть runtime PASS здесь
не заявляются.
