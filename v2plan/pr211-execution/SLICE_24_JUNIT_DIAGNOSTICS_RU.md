# Slice 24: доступная диагностика уже выполненного core CI

После потери local exec недоступен локальный разбор ZIP/XML, а полный core log
не возвращается connector (`Transport closed`). Чтобы продолжить точный triage,
добавлен отдельный `acceptance-diagnostics` job после существующего core matrix.

Новый stdlib reader читает uploaded XML этого же run/attempt. Он не импортирует
проект, не устанавливает зависимости и не запускает тесты. Все прежние workflow
bytes, selectors, Python matrix, required-ci dependencies и его условия сохранены.

На каждый Python lane считаются отдельно PASS/FAIL/ERROR/SKIP, исходный XML SHA256,
suite/testcase consistency и duplicate concrete IDs. Node ID восстанавливается
через реальный module prefix, сохраняя class и параметризацию. Суммирования matrix
нет. Полный JSON хранит все cases/messages/traces; console отдельно ограничена
для доставки: counts, module/first-cause summaries, focused failures. Число
непоместившихся console rows явно сообщается. Это ограничение логирования,
не порог качества/стоимости пользовательского MCP результата.

Независимый question_recovery_impl review: APPROVE после устранения первого
draft, печатавшего все 1900 failures. Финальные blobs: script
`43ff76490e416cc7423bfc619d7db41ef903177d`, CI
`2b515dc9e148e4c6bae8a72f1bce8350de848f7a`.
Artifact action pin взят из действующего P1 workflow. Existing required-ci
продолжает оценивать реальные test jobs; зелёная диагностика не означает зелёный CI.
Local AST/runtime **NOT RUN** из-за exec outage; первая execution ожидается в CI.
