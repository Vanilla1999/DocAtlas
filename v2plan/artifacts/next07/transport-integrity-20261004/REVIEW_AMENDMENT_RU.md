# Исправление только запуска pytest

Run 37235135829, SHA ee29388814276f36d4d6312bbc1b8c8c7a6a8c6a, artifact11315660204:
проверка frozen code и установка окружения прошли. Collection завершилась
pytest UsageError `diagnostic_unclassified` для research-модулей v2plan.
`no tests ran in 1.83s`; target/corpus/terminal SDK SKIPPED.

Причина: research-модули и tests/docs были переданы в одном pytest-процессе.
Конфигурация tests/conftest.py применяет tests/diagnostic_labels.py ко всему
collected inventory, а v2plan не входит в frozen product-test manifest.

Исправление только workflow: existing research checks выполняются прежним
отдельным pytest; две существующие product-test modules — вторым отдельным
pytest с собственными log/JUnit/exit code. Manifest, conftest, diagnostic guard,
code, corpus и assertions не меняются и не отключаются. Summary требует оба
exit code=0. Это исправление incompatible harness command, не algorithm retry.
Исходный invalid run сохранён. Review hashes4 файлов остаются неизменными.
