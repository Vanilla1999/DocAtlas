# G — frozen independent Dart code-QA oracle

Frozen before SWE pruning scores/host outputs for this case. Case **F-CODE-01**, narrow **ADAPTED Dart source-reading smoke**, not SWE-Bench, code execution, app navigation runtime or edit proof.

Exact question / task hint unchanged:

> How do openHelpChat and openWeb change the active tab, and what is the initial tab in TSDTabController?

Independently read baseline `tests/test_mcp_code_context_tool.py:16–65` at source snapshot `4849b8f796d9e3e25e2c49e58562ec6859978411`, not F's suggested answers as oracle. Baseline test-file SHA-256 `45e7ab21c550b56642ba1cba7ffd4c094bbdeda3fdc4e3f9d07f9aa2aa0dc53d`. Every fenced Dart listing in `F_assets/F_CODE_REFERENCE.md` independently occurs unchanged inside the original fixture's triple-quoted strings. Wrapper document SHA-256 **`151a1fc34cbb0d4ebfb768a0fa341ed15f576527304a718524d36f01e693432b`**. Coordinates below refer to this complete wrapper source as proposed `docs/code-reference.md`, not to fixture Python coordinates or synthetic concatenated Dart files.

## Required facts and exact original source witnesses

| Obligation | Exact quote | Half-open char/UTF-8 byte span | Wrapper lines |
|---|---|---|---|
| openHelpChat passes helpChat to its controller | `void openHelpChat() {\n    controller.switchTo(FlutterTabType.helpChat);\n  }` | `[738,813)` | 32–34 |
| openWeb passes web to its controller | `void openWeb() {\n    controller.switchTo(FlutterTabType.web);\n  }` | `[817,882)` | 36–38 |
| Initial state is web, not helpChat | `FlutterTabType current = FlutterTabType.web;` | `[1060,1104)` | 48 |
| Controller switchTo assigns passed type, explaining state change | `void switchTo(FlutterTabType type) {\n    current = type;\n  }` | `[1108,1168)` | 50–52 |

The wrapper is ASCII; char and UTF-8 byte spans agree. Full correct answer must connect each notifier method to its `switchTo` argument **and** the controller assignment, and identify initial `current=web`. Independent expected semantics: calling openHelpChat sets controller.current to helpChat through switchTo; openWeb sets it to web; initial current is web. Merely finding enum labels or function names is incomplete. No code execution is required or permitted for this QA claim, and no actual UI/network/app side effect may be asserted from the text alone.

For source fact delivery, require complete method/assignment/default witnesses in actually emitted original-source spans. For host correctness, semantically equivalent concise wording is accepted only with original evidence IDs and exact supporting citations; a one-line call citation supports the called method/argument but cannot by itself prove switchTo's assignment implementation. Missing assignment/default must be an explicit gap, not inferred from memory or method naming.

## Paired public/pruning outcomes

- One real public B1 project-doc preparation/read, finite source-of-truth catalog, exact source bytes/hash/coordinates and false answer/edit authority. Actual public packet becomes identical baseline input for no-pruning and pruning branches. Do not insert missing lines chosen by this oracle after acquisition.
- Whole wrapper hash and source policy bindings immutable. Returned snippets/kept runs are exact original continuous spans with omission boundaries outside quotes. Dropping required methods/default/assignment is fact-delivery FAIL even with a better ratio; correctly declining with insufficient context is honest grounding but not task solved.
- Generated answer claims/citations checked separately from retained-span facts, ranking or compressor self-scores. Host sees question/task hint and actual selected public source text/metadata only, not this oracle/F proposal.
- No code edits, Flutter UI behavior, integration runtime of the Dart listing, or SWE-Bench success can be claimed. This short synthetic fixture on known repo source cannot establish long-code savings/generalization. Keep documentation50 and code-QA results separate.
- No public acquisition/pruning/host output for this case has been reviewed at freeze. Runtime outcome **PENDING**. Source-only QA may succeed without executing Dart, but must be labelled accordingly.
