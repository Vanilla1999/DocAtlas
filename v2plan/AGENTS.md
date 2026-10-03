# Research: обязательная граница упрощения

Мы уже переусложнили relevance/admission. Новая правка должна заменять
конкурирующее решение, а не добавлять ещё один fallback или rescue.

- Перед изменением назвать заменяемую обязанность и способ проверки.
- Не добавлять исключения под case, библиотеку или relation, словари и threshold tuning.
- Не смешивать изменения retrieval, compiler, admission и selector в одном trial.
- Source/security/version/scope/freshness/span/request и identity/applicability
  guards сохраняются. Read context не выдаёт proof, coverage или edit permission.
- Production/defaults не переключать из успешного research run автоматически.
- Если общий контракт не сформулирован или результат требует новых исключений,
  остановиться и записать ограничение. Число tests/runs не доказывает качество.
