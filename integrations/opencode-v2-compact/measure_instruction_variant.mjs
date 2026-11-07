// Offline text sizing of one preserved provider request, not model acceptance.
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { isDeepStrictEqual, parseArgs } from "node:util";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { conciseToolDescriptions } from "./profile/index.js";

const { values } = parseArgs({ options: {
  capture: { type: "string" }, python: { type: "string" },
}, strict: true });
if (!values.capture || !values.python || !path.isAbsolute(values.python)) {
  throw new Error("Required: --capture saved-events.jsonl --python /absolute/installed-python");
}
const here = path.dirname(fileURLToPath(import.meta.url));
const capture = readFileSync(values.capture, "utf8");
const events = capture.split(/\r?\n/u).filter(Boolean).map(line => JSON.parse(line));
const sent = events.find(event => event.type === "experimental.ws.send");
if (!sent) throw new Error("No saved provider request; no replay or inference is attempted");
const original = JSON.parse(sent.data);
const tools = original.tools;
if (!Array.isArray(tools) || typeof original.instructions !== "string") {
  throw new Error("Expected preserved Responses request instructions and tool definitions");
}
const contexts = tools.filter(tool => tool.name?.endsWith("_get_docs_context"));
if (contexts.length !== 1) throw new Error("Expected one explicit DocAtlas tool prefix");
const serverName = contexts[0].name.slice(0, -"_get_docs_context".length);
const definitions = Object.fromEntries(tools.map(tool => [tool.name, {
  description: tool.description, input: tool.parameters,
}]));
const transformed = conciseToolDescriptions(definitions, serverName);
const candidateTools = tools.map(tool => ({ ...tool,
  description: transformed[tool.name].description, parameters: transformed[tool.name].input,
}));

// Independent annotation-insensitive comparison of the saved public schema.
// Keep property names (including a potential property literally "description")
// and every nested validation constraint; only root/direct property annotations
// are permitted to differ in this candidate.
function structuralSchema(schema) {
  const result = structuredClone(schema);
  delete result.description;
  for (const property of Object.values(result.properties ?? {})) {
    if (property && typeof property === "object" && !Array.isArray(property)) delete property.description;
  }
  return result;
}
if (!tools.every((tool, index) => isDeepStrictEqual(
  structuralSchema(tool.parameters), structuralSchema(candidateTools[index].parameters)))) {
  throw new Error("Structural schema changed; refusing to report a comparable description-only estimate");
}
const standard = readFileSync(path.join(here, "profile/mcp.txt"), "utf8").trim();
const concise = readFileSync(path.join(here, "profile/mcp-concise.txt"), "utf8").trim();
if (original.instructions.split(standard).length !== 2) {
  throw new Error("Saved request does not contain exactly one unchanged standard MCP paragraph");
}
const candidateInstructions = original.instructions.replace(standard, concise);
const categories = [
  ["instructions", original.instructions, candidateInstructions],
  ["tool_schemas", JSON.stringify(tools), JSON.stringify(candidateTools)],
];
const { counts } = JSON.parse(execFileSync(values.python,
  ["-I", path.join(here, "count_tokens.py")], {
    input: JSON.stringify(categories.flatMap(([, before, after]) => [before, after])),
    encoding: "utf8", timeout: 30000,
  }));
const sha = value => createHash("sha256").update(value).digest("hex");
const measurements = Object.fromEntries(categories.map(([name, before, after], index) => [name, {
  standard: counts[index * 2], concise_v1: counts[index * 2 + 1],
  saved_tokens: counts[index * 2] - counts[index * 2 + 1],
  standard_sha256: sha(before), concise_sha256: sha(after),
}]));
console.log(JSON.stringify({
  boundary: "Offline o200k text estimate on one preserved request using the real annotation transform; not live provider usage, client acceptance or answer quality.",
  provider_calls: 0, tool_calls: 0, model_inference: 0,
  capture_sha256: sha(capture), transform_sha256: sha(readFileSync(path.join(here, "profile/index.js"))),
  tool_names: tools.map(tool => tool.name), structural_schema_unchanged: true,
  measurements,
  combined_standard: counts[0] + counts[2], combined_concise_v1: counts[1] + counts[3],
  note: "Original question, history/results and tool-call trajectory are not generated or remeasured. No full-session saving is inferred.",
}, null, 2));
