| ID | Замороженное требование | off | mini |
|---|---|---:|---:|
| F01.1 | get_docs_context retrieves documentation | 1 | 1 |
| F01.2 | prepare_docs performs authorized lifecycle | 1 | 1 |
| F01.3 | docs_status reports status | 1 | 1 |
| F02.1 | installer installs DocAtlas and registers OpenCode | 1 | 1 |
| F02.2 | agent can be selected noninteractively | 1 | 1 |
| F03.1 | installation binds but does not index documents | 1 | 1 |
| F04.1 | doc-atlas install opencode --project | 0 | 1 |
| F04.2 | --project-path selects another absolute project | 0 | 1 |
| F05.1 | not_prepared and member_store_uninitialized mean unprepared store, not permission error | 1 | 1 |
| F05.2 | confirmed current hashes and mutation then retry original | 1 | 1 |
| F06.1 | --config then ./docatlas.yaml then ~/.docatlas/docatlas.yaml | 1 | 1 |
| F06.2 | relative index paths resolved from config file | 1 | 1 |
| F07.1 | GitBook, Mintlify, web, GitHub and local files | 1 | 1 |
| F07.2 | local Markdown, text, HTML, PDF, DOCX, RTF | 1 | 1 |
| F08.1 | docatlas.project-docs.yaml explicit literal paths, no recursive/glob discovery | 0 | 1 |
| F08.2 | role scope module path authority status impact | 0 | 1 |
| F09.1 | mutation confirm true, trusted store, current hashes and generation | 0 | 0 |
| F09.2 | no mutation means no writes; upsert neither prunes nor writes vectors | 1 | 0 |
| F10.1 | explicit library and exact version | 1 | 1 |
| F10.2 | no implicit latest or unauthorized discovery | 0 | 0 |
| F11.1 | project repo only | 1 | 1 |
| F11.2 | module requires exact module_path | 1 | 1 |
| F11.3 | module_path implies module | 1 | 1 |
| F11.4 | all repo and modules without filters | 1 | 1 |
| F12.1 | path identity authority scope hash verbatim snippet and local coordinates | 1 | 1 |
| F12.2 | attribution does not confer permissions | 1 | 1 |
| F13.1 | mismatch before retrieval; connect correct project | 1 | 1 |
| F13.2 | do not use subfolder as project; preserve scope | 0 | 0 |
| F14.1 | network preparation requires explicit permitted source and consent | 1 | 1 |
| F14.2 | discovery is not indexing consent | 0 | 0 |
| F15.1 | poll docs_status using returned job id | 1 | 1 |
| F15.2 | retry unchanged original after verified success | 1 | 1 |
| F16.1 | tracing off by default; DOCATLAS_TRACE=1 or --trace enables | 1 | 1 |
| F16.2 | MCP diagnostic stderr separate from stdout | 1 | 1 |
| F17.1 | integration, installed stdio, real client and production smoke are distinct | 1 | 0 |
| F17.2 | new tests integration level and above | 0 | 0 |
| F18.1 | source checked combined candidate selection, relevance and redundancy | 1 | 1 |
| F18.2 | real delivery budget, attribution and unverified coverage | 1 | 1 |
| F19.1 | preview and review plan digest, stop workers, apply exact digest | 1 | 0 |
| F19.2 | shared index not deleted by guessing ownership | 1 | 0 |
| F20.1 | delivery error not missing docs | 1 | 0 |
| F20.2 | do not retry unchanged or broaden scope; fix delivery and inspect actually visible result | 1 | 0 |
