# Только execution inputs V3

`cases.json` содержит исходные вопросы, split и логический project. `corpus/<project>/` содержит markdown с относительными путями, которые необходимо сохранить без изменения bytes. Каждый project материализуется отдельно; объединение семейства holdout с calibration запрещено. Scope публичного `get_docs_context` — `project`, lookup_queries отсутствуют. Версия не запрашивается: ожидается реальный `unversioned`, не выдуманная synthetic версия.

В `corpus/legacy_priority/` сохранены все пять документов старой fixture, хотя выполняются только два numeric controls. Это сохраняет конкурентные retrieval operands. Новый абсолютный project_path, generation и IDs нужно записать, а не копировать из старого raw. Старые outputs не являются парным новым baseline.

Execution inputs не содержат oracle, gold spans или answer labels. Авторам product patch не передавать `../private/`, calibration labels передавать отдельно только после фиксации контрактов A/B. Holdout допускается исполнять только после заморозки patch/параметров; ответы и inputs модели сохранять до review без repairs/retries. Этот пакет сам по себе не разрешает исполнение.
