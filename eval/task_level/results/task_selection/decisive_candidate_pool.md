# Decisive Real-Project Candidate Pool

Sanitized candidate pool mined from local projects under `/home/viadmin/StudioProjects/` plus existing historical NBO/Docmancer task shapes. Raw git history, private remotes, credentials, customer data, and exact private business details are intentionally excluded.

Scoring thresholds for `recommended=true`: DocAtlas relevance >=7, repo-only difficulty >=7, fairness >=8, privacy risk <=3, fixture cost <=7.

## decisive_nbo_generated_policy_source_001

- source_project: nbo
- candidate_type: generated_file_trap
- why repo_only may struggle: The symptom is visible near a generated output stub, but the durable fix must happen in the source model and regenerated-output policy lives in separate docs.
- why DocAtlas should help: Project docs and source comments identify source-of-truth and generated-file boundaries before the agent edits the tempting generated file.
- visible context required: docs/generated-source.md, lib/modules/permission/ARCHITECTURE.md, permission_info.dart source model, generated output stub
- tempting wrong fixes: edit *.freezed.dart, add a provider-only helper, hard-code a public-test-only branch
- privacy risk: low; can sanitize to permission module only
- fixture size estimate: medium
- scores: DocAtlas 8/10; repo_only difficulty 8/10; fairness 9/10; privacy risk 1/10; fixture cost 5/10
- selection status: implemented and screened in `decisive_nbo_generated_policy_source_001_screening_001`; rejected_too_easy because `repo_only_strict_offline` resolved 2/2 with policy clean, artifact integrity clean, and fairness clean
- recommended: true
- reason: Meets thresholds; high generated-file and distributed-doc relevance. Previous similar narrow task was too easy, so this would need a larger snapshot.

## decisive_nbo_permission_handler_version_001

- source_project: nbo
- candidate_type: dependency_trap
- why repo_only may struggle: A plausible patch may use latest permission_handler APIs or unrelated Android media permissions instead of the lockfile-pinned 11.4.0 API.
- why DocAtlas should help: DocAtlas can surface pubspec.lock and local dependency notes without web access or model-memory guesses.
- visible context required: pubspec.lock, docs/dependencies.md, permission service mapping, fake permission status tests
- tempting wrong fixes: upgrade dependency, use Permission.photos/videos/audio, patch only Android branch
- privacy risk: low after manifest/module sanitization
- fixture size estimate: medium-large
- scores: DocAtlas 8/10; repo_only difficulty 8/10; fairness 8/10; privacy risk 1/10; fixture cost 7/10
- selection status: implemented and screened in `decisive_nbo_permission_handler_version_001_screening_001`; rejected_too_easy because `repo_only_strict_offline` resolved 2/2 with policy clean, artifact integrity clean, and fairness clean
- recommended: true
- reason: Meets thresholds at the maximum allowed fixture cost; implement only if a sanitized lockfile/version snapshot can stay within scope.

## decisive_nbo_cross_module_gate_large_001

- source_project: nbo
- candidate_type: cross_module_contract
- why repo_only may struggle: Two flows have similar local gates; a one-flow fix passes public symptom but violates shared permission contract documented elsewhere.
- why DocAtlas should help: Retrieved architecture docs should point to PermissionService as the canonical gate and list both browser/scan flow contracts.
- visible context required: docs/permission-architecture.md, docs/browser-flow.md, docs/scan-flow.md, browser gate, scan gate, permission service
- tempting wrong fixes: fix only failing flow, duplicate interpretation in each gate, relax hidden gate assertion
- privacy risk: low if permission domain is sanitized
- fixture size estimate: large
- scores: DocAtlas 9/10; repo_only difficulty 8/10; fairness 9/10; privacy risk 1/10; fixture cost 7/10
- recommended: true
- reason: Meets thresholds at the maximum allowed fixture cost; current narrow implementation was too easy, so a redesigned larger fixture must preserve fairness without overspecifying the issue.

## decisive_nbo_browser_scan_policy_001

- source_project: nbo
- candidate_type: multi_doc_architecture_constraint
- why repo_only may struggle: Public failure can be fixed by adding notification to one flow, but hidden contracts require platform/version-specific preflight and deferred background location.
- why DocAtlas should help: Project docs connect browser/scan policy, Android 13 notification behavior, and deferred background-location constraint.
- visible context required: docs/browser-scan-preflight.md, docs/permission-notifications.md, docs/permission-location.md, pubspec.lock
- tempting wrong fixes: request notification on all Android versions, request locationAlways during preflight, edit provider instead of service
- privacy risk: low
- fixture size estimate: medium
- scores: DocAtlas 9/10; repo_only difficulty 7/10; fairness 9/10; privacy risk 1/10; fixture cost 5/10
- recommended: true
- reason: Meets thresholds, but an earlier narrower implementation screened too easy; needs less explicit issue text/larger distractor surface.

## decisive_docmancer_vector_timeout_fallback_001

- source_project: docmancer
- candidate_type: private_local_workflow
- why repo_only may struggle: The failure spans vector indexing timeout, fallback metadata, and benchmark accounting; local code alone has multiple plausible counters to increment.
- why DocAtlas should help: Docs explain retrieval status, fallback semantics, and what can count as workflow success versus vector robustness.
- visible context required: docs/research/task-level-agent-benchmark.md, eval/task_level/execution.py, artifact integrity tests, runner result schema
- tempting wrong fixes: count fallback as vector retrieval success, drop timeout flag, mark all DocAtlas context as used
- privacy risk: low public repo
- fixture size estimate: medium
- scores: DocAtlas 8/10; repo_only difficulty 7/10; fairness 8/10; privacy risk 1/10; fixture cost 5/10
- recommended: true
- reason: Meets thresholds, but it is self-referential to DocAtlas and should be used cautiously as regression, not external proof.

## decisive_docmancer_policy_audit_network_001

- source_project: docmancer
- candidate_type: historical_fix
- why repo_only may struggle: Policy audit distinguishes browser-word mentions, actual network attempts, web-audited allowances, and strict-offline violations across logs.
- why DocAtlas should help: Benchmark docs state isolation policy and audit semantics, preventing overbroad greps or undercounting network use.
- visible context required: docs/research/task-level-agent-benchmark.md, tests/task_level/test_policy_baselines.py, eval/task_level/policy audit code
- tempting wrong fixes: treat the word browser as web use, allow network in strict offline, hide network attempts in notes
- privacy risk: low
- fixture size estimate: medium
- scores: DocAtlas 7/10; repo_only difficulty 7/10; fairness 8/10; privacy risk 1/10; fixture cost 4/10
- recommended: true
- reason: Meets thresholds but source project is benchmark itself; useful for harness validation more than external agent-value proof.

## decisive_docmancer_actionability_contract_001

- source_project: docmancer
- candidate_type: adr_mismatch
- why repo_only may struggle: Checklist generation must include visible requirements but avoid hidden-only symbols; naive implementation leaks oracle requirements.
- why DocAtlas should help: Local benchmark docs and fairness reviews specify discoverability constraints and visible-source mapping.
- visible context required: actionability tests, fairness review docs, task manifest schema, expected_project_docs
- tempting wrong fixes: copy hidden requirements into checklist, invent parameter names, omit source references
- privacy risk: low
- fixture size estimate: small-medium
- scores: DocAtlas 7/10; repo_only difficulty 7/10; fairness 8/10; privacy risk 1/10; fixture cost 4/10
- recommended: true
- reason: Meets thresholds; caveat: self-referential benchmark code may not generalize.

## decisive_mobile_flutter_generated_l10n_001

- source_project: mobile-scout-flutter
- candidate_type: generated_file_trap
- why repo_only may struggle: Flutter localization/generated files often tempt direct edits while source ARB/config is canonical.
- why DocAtlas should help: Project docs/manifests can surface generation policy and build_runner/l10n configuration.
- visible context required: l10n.yaml or build config, README generation notes, ARB/source files, generated Dart output
- tempting wrong fixes: edit generated localization Dart, change generated registry, ignore pinned Flutter tooling
- privacy risk: medium until sanitized; mobile domain may contain private labels
- fixture size estimate: medium
- scores: DocAtlas 8/10; repo_only difficulty 7/10; fairness 7/10; privacy risk 4/10; fixture cost 6/10
- recommended: false
- reason: Fails privacy/fairness thresholds until source is reviewed and sanitized.

## decisive_krakend_config_contract_001

- source_project: krakend-service-helpdesk-proxy
- candidate_type: migration_or_version_mismatch
- why repo_only may struggle: Gateway config syntax/version and endpoint policy can be split across templates, docs, and generated config output.
- why DocAtlas should help: DocAtlas can retrieve local ADR/runbook snippets and versioned config constraints before editing JSON templates.
- visible context required: README/runbook, krakend config templates, version manifest, public smoke tests
- tempting wrong fixes: edit generated config, use wrong KrakenD version field, change route shape outside documented proxy contract
- privacy risk: medium-high due service/domain configuration
- fixture size estimate: medium-large
- scores: DocAtlas 8/10; repo_only difficulty 8/10; fairness 6/10; privacy risk 5/10; fixture cost 7/10
- recommended: false
- reason: Interesting but privacy and sanitization risk too high for immediate fixture.

## decisive_flutter_keycloak_version_001

- source_project: flutter-keycloak
- candidate_type: dependency_trap
- why repo_only may struggle: Auth package APIs change across versions and web/native setup docs are easy to conflate.
- why DocAtlas should help: Local dependency pins and setup docs could prevent latest-only API or platform-mismatch fixes.
- visible context required: pubspec.lock, auth README, platform setup files, public auth tests
- tempting wrong fixes: upgrade auth dependency, mix web-only and native APIs, hard-code callback URL
- privacy risk: medium due auth domain
- fixture size estimate: medium
- scores: DocAtlas 8/10; repo_only difficulty 7/10; fairness 7/10; privacy risk 4/10; fixture cost 6/10
- recommended: false
- reason: Auth/privacy boundary needs human sanitization before fixture.

## decisive_android_keyboard_input_contract_001

- source_project: android-keyboard
- candidate_type: cross_module_contract
- why repo_only may struggle: IME behavior can require agreement between manifest, service lifecycle, and key event handling docs.
- why DocAtlas should help: Project docs/manifest constraints should guide the patch away from a local key-handler-only fix.
- visible context required: AndroidManifest.xml, IME service docs, input handling code, instrumentation/fake tests
- tempting wrong fixes: patch only key event map, change manifest permission without service contract, ignore lifecycle callback
- privacy risk: low-medium
- fixture size estimate: large
- scores: DocAtlas 7/10; repo_only difficulty 7/10; fairness 7/10; privacy risk 3/10; fixture cost 8/10
- recommended: false
- reason: Fixture cost and fairness uncertainty too high.

## decisive_viscanner_scan_pipeline_001

- source_project: viscanner
- candidate_type: multi_doc_architecture_constraint
- why repo_only may struggle: Scanner pipeline bugs often have tempting UI-layer fixes while the contract belongs in acquisition/preprocessing modules.
- why DocAtlas should help: Architecture docs can surface the pipeline boundary and generated/native output constraints.
- visible context required: pipeline README/ADR, scanner service, UI caller, test fixtures
- tempting wrong fixes: fix only UI callback, edit generated/native artifact, bypass preprocessing contract
- privacy risk: medium; may include customer/device details
- fixture size estimate: large
- scores: DocAtlas 8/10; repo_only difficulty 8/10; fairness 6/10; privacy risk 5/10; fixture cost 8/10
- recommended: false
- reason: High potential but not safe/cheap enough without deeper sanitization.
