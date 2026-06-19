# Prompt 06 — First-run DX, Doctor and Onboarding

Ты — DX lead / technical product designer для CLI devtools и AI coding agent tooling.

## Контекст

Docmancer — local-first docs context tool. У него есть:

- `docmancer setup`;
- `docmancer ingest`;
- `docmancer add`;
- `docmancer query`;
- `docmancer doctor`;
- `docmancer inspect`;
- managed Qdrant lifecycle;
- FastEmbed model cache;
- local SQLite;
- optional cloud embeddings;
- agent skill installation;
- MCP docs server;
- MCP API packs.

Проблема: first-run может быть сложным. Пользователю нужно понимать Qdrant, model downloads, vector fallback, config drift, agent skill installation/restart, CLI vs MCP modes.

## Задача

Спроектируй first-run DX и action-oriented diagnostics для Docmancer.

## Что нужно выдать

1. **5-minute happy path**
   - Для нового пользователя.
   - Для coding agent user.
   - Для local docs folder.
   - Для web docs URL.
   - Для MCP docs server.

2. **Onboarding flows**
   - CLI-first.
   - MCP-first.
   - Agent-skill-first.
   - Project-local config.

3. **Setup UX**
   - Что должен делать `docmancer setup`.
   - Что спрашивать интерактивно.
   - Что делать non-interactive.
   - Как объяснять downloads.
   - Как объяснять local-first/no API keys.

4. **Doctor redesign**
   - Что должен проверять `docmancer doctor`.
   - Как сделать output action-oriented.
   - Как группировать severity.
   - Как давать exact remediation commands.
   - Как показывать agent integration health.

5. **Inspect / list UX**
   - Что должен показывать `list`.
   - Что должен показывать `inspect`.
   - Как показывать stale docs, failed pages, vector drift.

6. **Failure modes and remediation**
   - Qdrant missing/down.
   - Model download failed.
   - Cloud API key missing.
   - Vector collection mismatch.
   - Empty index.
   - Bad docs extraction.
   - Agent skill installed but app not restarted.
   - MCP docs server not configured.

7. **Documentation IA**
   - README structure.
   - Separate quickstarts.
   - Troubleshooting.
   - Advanced sections.
   - How to present docs-RAG vs API packs.

8. **Acceptance criteria**
   - Time-to-first-success.
   - Setup completion rate.
   - Doctor remediation coverage.
   - User confusion reduction signals.

9. **Test plan**
   - Clean machine tests.
   - Offline/air-gapped tests.
   - No Qdrant tests.
   - No API key tests.
   - Agent config tests.

10. **Implementation plan**
    - MVP.
    - v1.
    - v2.

## Ограничения

- Не скрывай сложность ложными обещаниями.
- Не делай onboarding enterprise-heavy.
- Сохрани local-first identity.
- Учитывай, что agent skills/config changes may require restart.

## Формат ответа

Дай proposed CLI outputs/examples, checklist-based doctor design и phased plan. В конце дай `Must / Should / Could`.
