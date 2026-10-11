# Main-flow documentation comparison

Development evaluation, not a holdout. Ten Russian questions are frozen in
`questions.json` before retrieval. Expected facts are authored from the source
documents independently of either tool's output and are NOT indexed.

The identical source corpus is the concatenation of
`docs/main-flow-logging.md` and `docs/main-flow-evaluation.md`, with source-path
headings. `corpus.md` is generated verbatim; its manifest records SHA-256 hashes.
Only this corpus is indexed in each isolated target. Scope: the new main-flow
logging feature and this project's evaluation policy, not the entire repository.

DocAtlas uses the new branch through a real MCP stdio client. Grounded uses its
MCP `search_docs` tool against the same publicly pinned corpus URL. Questions
are identical, with no paraphrased lookup hints or retries to improve scores.
Returned evidence is assessed separately from the answers synthesized from it.
Latency includes tool/transport overhead and is not a controlled performance test.
