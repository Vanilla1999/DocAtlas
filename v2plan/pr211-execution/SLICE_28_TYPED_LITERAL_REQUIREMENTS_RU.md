# Slice 28: типизированные literal witnesses в трёх formatter tests

Три положительных случая на ec85a49 возвращают whole-window data, но completeness
остаётся partial: тесты передают отдельный symbol как plain string required_fact.
Текущий контракт явно различает exact_term (literal occurrence) и required_fact
(равенство целой answer unit). Подмена expected complete на partial потеряла бы
исходный guard; production matcher не ослабляется.

RareExactSymbol, MCP, fetch/index и format_packet передаются как typed exact_term.
Полное предложение про сохранение stable child citations остаётся required_fact.
У formatter fixture уже присутствует src/formatter.py; этот существующий путь
объявлен required_evidence_paths. Контракт проверяет source identity, а basename
не становится дополнительным требованием к телу code window.

Все исходные вопросы, source texts, paths, hashes и coordinates сохранены.
Проверки complete, exact full text, no edit permission, untrusted document data
и отвержения подменённого текста с пересчитанным hash/span остаются. Сохраняются
20 test names и два helpers; новый blanket output cap не вводится.

Independent source review question_recovery_impl: APPROVE для blob
aba7c39d44593cfaf02b33e53f21d7d2450ca297 относительно 3f3de127.
Проверены build_requirements и _legacy_requirement_matches_unit. Local AST/runtime
NOT RUN из-за exec transport outage; фактический результат проверяется PR CI.
