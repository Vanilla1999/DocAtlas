import { createHash, randomUUID } from "node:crypto";
import { realpath } from "node:fs/promises";
import path from "node:path";

const VERSION = "host-v1";
const AUDIT_KEY = "docatlas_language_preflight";
const TIMEOUT_MS = 10000;
const MAX_RECORDS = 256;
const BINDING_FIELDS = ["project_path", "project_id", "workspace_path"];
const HASH = /^[0-9a-f]{64}$/;
const TAG = /^[a-z]{2,8}(?:-[a-z0-9]{1,8})*$/;
const STATUSES = new Set(["declared", "mixed", "partial", "unknown"]);

class DocumentationLanguagePreflightError extends Error {
  constructor(code) {
    super(code);
    this.name = "DocumentationLanguagePreflightError";
    this.code = code;
  }
}

const fail = code => { throw new DocumentationLanguagePreflightError(code); };
const object = value => value !== null && typeof value === "object" && !Array.isArray(value);
const digest = value => createHash("sha256").update(value).digest("hex");
const count = value => Number.isSafeInteger(value) && value >= 0;
const identity = value => typeof value === "string" && value.length > 0 && value.length <= 256;
const promptID = (sessionID, messageID) => digest(JSON.stringify([sessionID, messageID])).slice(0, 16);
const recordKey = (sessionID, messageID, admissionID) => JSON.stringify([sessionID, messageID, admissionID]);

function sameBinding(actual, expected) {
  return object(actual) && Object.keys(actual).length === BINDING_FIELDS.length &&
    BINDING_FIELDS.every(key => actual[key] === expected[key]);
}

function languageResult(result, binding) {
  // The current native MCP executor and the existing compact adapter both
  // publish authoritative content. Never recover a hint from output/_meta when
  // content is missing, an emergency envelope, or an unsupported multipart body.
  if (!object(result) || result.isError === true || result.error !== undefined) {
    fail("documentation_language_preflight_envelope_invalid");
  }
  const content = result.content;
  const text = typeof content === "string" ? content :
    Array.isArray(content) && content.length === 1 && content[0]?.type === "text" ? content[0].text : undefined;
  if (typeof text !== "string" || Buffer.byteLength(text, "utf8") > 65536) {
    fail("documentation_language_preflight_envelope_invalid");
  }
  let payload;
  try { payload = JSON.parse(text); }
  catch { fail("documentation_language_preflight_envelope_invalid"); }
  if (!object(payload) || payload.tool !== "docs_status" || payload.action !== "project" ||
      payload.isError === true || payload.error !== undefined || payload.status !== undefined ||
      payload.kind !== undefined || payload.mcp_compaction !== undefined || !object(payload.project) ||
      payload.project.project_path !== binding.project_path || !sameBinding(payload.project_binding, binding)) {
    fail("documentation_language_preflight_binding_or_envelope_mismatch");
  }
  const language = payload.documentation_language;
  if (!object(language) || !STATUSES.has(language.status) || language.scope !== "project" ||
      language.module_path !== undefined || language.hint_only !== true ||
      !Array.isArray(language.languages) || language.languages.length > 16 ||
      language.languages.some(tag => typeof tag !== "string" || tag.length > 63 ||
        !TAG.test(tag) || tag === "und" || tag === "mul") ||
      new Set(language.languages).size !== language.languages.length) {
    fail("documentation_language_preflight_language_invalid");
  }
  const languages = [...language.languages];
  const projected = { status: language.status, languages, scope: "project", hint_only: true,
    basis: language.basis };
  if (language.basis === "not_declared") {
    if (language.status !== "unknown" || languages.length !== 0 ||
        ["catalog_sha256", "snapshot_sha256", "source_count", "unknown_sources"].some(key =>
          language[key] !== undefined)) fail("documentation_language_preflight_language_invalid");
    return projected;
  }
  if (language.basis !== "catalog_declaration" || typeof language.catalog_sha256 !== "string" ||
      !HASH.test(language.catalog_sha256) || typeof language.snapshot_sha256 !== "string" ||
      !HASH.test(language.snapshot_sha256) || !count(language.source_count) ||
      language.source_count === 0 || language.source_count > 500 || !count(language.unknown_sources) ||
      language.unknown_sources > language.source_count ||
      language.status === "declared" && (languages.length !== 1 || language.unknown_sources !== 0) ||
      language.status === "mixed" && (languages.length < 2 || language.unknown_sources !== 0) ||
      language.status === "partial" && (languages.length === 0 || language.unknown_sources === 0) ||
      language.status === "unknown" && (languages.length !== 0 || language.unknown_sources !== language.source_count)) {
    fail("documentation_language_preflight_language_invalid");
  }
  return { ...projected, catalog_sha256: language.catalog_sha256,
    snapshot_sha256: language.snapshot_sha256, source_count: language.source_count,
    unknown_sources: language.unknown_sources };
}

function modelHint(record, sessionID, messageID) {
  return { status: record?.status ?? "unknown", languages: record ? [...record.languages] : [],
    scope: "project", prompt_id: identity(messageID) ? promptID(sessionID, messageID) : null,
    hint_only: true };
}

// OpenCode 2.2.5's public ctx.tool.list() includes ToolInfo.execute(input,
// {sessionID, agent, messageID, id, signal, progress}). The native MCP executor
// retains permission.assert and the registered adapter wrappers. Calling this
// executor does not run generic execute.before/after hooks; fixed host arguments
// must therefore pass the shared project guard explicitly before execution.
export function createLanguagePreflight({ ctx, root, binding, statusTool, lifecycle, projectArgs }) {
  if (typeof root !== "string" || !path.isAbsolute(root) || path.normalize(root) !== root ||
      !object(binding) || !sameBinding(binding, binding) || binding.project_path !== root ||
      binding.project_id !== `local:${digest(root)}` || typeof binding.workspace_path !== "string" ||
      !path.isAbsolute(binding.workspace_path) || binding.workspace_path !== ctx.location?.directory ||
      typeof statusTool !== "string" || typeof projectArgs !== "function" || !lifecycle?.signal) {
    fail("documentation_language_preflight_configuration_invalid");
  }
  // Copy the trusted builder output; neither a prompt nor a tool result can
  // replace this project's binding. No persistent metadata is a cache authority.
  const trustedBinding = Object.freeze(Object.fromEntries(BINDING_FIELDS.map(key => [key, binding[key]])));
  const records = new Map();
  const pending = new Set();
  let disposed = false;
  const active = () => {
    if (disposed || lifecycle.signal.aborted) fail("documentation_language_preflight_unloaded");
  };
  const admit = async (event, toolInfo) => {
    active();
    if (!identity(event.sessionID) || !identity(event.messageID) ||
        toolInfo?.id !== statusTool || typeof toolInfo.execute !== "function") {
      fail("documentation_language_preflight_context_invalid");
    }
    if (await realpath(root) !== root || await realpath(trustedBinding.workspace_path) !== trustedBinding.workspace_path) {
      fail("documentation_language_preflight_binding_changed");
    }
    const session = await ctx.session.get({ sessionID: event.sessionID });
    if (session?.id !== event.sessionID || session.location?.directory !== trustedBinding.workspace_path ||
        session.location?.workspaceID !== ctx.location.workspaceID) {
      fail("documentation_language_preflight_session_mismatch");
    }
    // The explicit trusted target lets the server reject a differently bound
    // project before inspection, not only when we inspect the returned binding.
    const input = { action: "project", include_language: true, project_path: root };
    await projectArgs(input);
    active();
    const controller = new AbortController();
    const unload = () => controller.abort(new DocumentationLanguagePreflightError("documentation_language_preflight_unloaded"));
    lifecycle.signal.addEventListener("abort", unload, { once: true });
    pending.add(controller);
    const timeout = setTimeout(() => controller.abort(new DocumentationLanguagePreflightError(
      "documentation_language_preflight_timeout")), TIMEOUT_MS);
    const started = performance.now();
    const admissionID = randomUUID().replaceAll("-", "");
    let rejectOnAbort;
    const interrupted = new Promise((_, reject) => {
      rejectOnAbort = () => reject(controller.signal.reason);
      controller.signal.addEventListener("abort", rejectOnAbort, { once: true });
    });
    try {
      const execution = Promise.resolve().then(() => {
        active();
        if (controller.signal.aborted) throw controller.signal.reason;
        return toolInfo.execute(input, {
          sessionID: event.sessionID, messageID: event.messageID, agent: session.agent,
          id: `call_docatlas_language_${admissionID}`, signal: controller.signal,
          progress: async () => {},
        });
      });
      // The installed native executor honours signal. This additional race
      // bounds prompt admission even if a later wrapper ignores cancellation;
      // it does not claim that such an unsupported wrapper stopped its work.
      // Promise.race consumes a late rejection from execution as well.
      const result = await Promise.race([execution, interrupted]);
      active();
      if (controller.signal.aborted) throw controller.signal.reason;
      const projected = languageResult(result, trustedBinding);
      const audit = { version: VERSION, admission_id: admissionID, ...projected,
        source_status: projected.status, project_binding: { ...trustedBinding }, binding_validated: true,
        prompt_id: promptID(event.sessionID, event.messageID), calls: 1,
        elapsed_ms: Math.round(performance.now() - started), timeout_ms: TIMEOUT_MS };
      // A nonce distinguishes concurrently prepared submissions with the same
      // message ID. OpenCode persists only the winning admission's metadata.
      const key = recordKey(event.sessionID, event.messageID, admissionID);
      records.set(key, Object.freeze({ ...projected, languages: Object.freeze([...projected.languages]) }));
      // Eviction can only remove a hint (yielding unknown), never reuse another
      // turn's result. Bound host memory without retaining questions/documents.
      while (records.size > MAX_RECORDS) records.delete(records.keys().next().value);
      event.metadata = { ...event.metadata, [AUDIT_KEY]: audit };
    } finally {
      clearTimeout(timeout);
      lifecycle.signal.removeEventListener("abort", unload);
      controller.signal.removeEventListener("abort", rejectOnAbort);
      pending.delete(controller);
    }
  };
  const inject = event => {
    active();
    if (!identity(event.sessionID) || !Array.isArray(event.messages) || !Array.isArray(event.system)) {
      fail("documentation_language_preflight_context_invalid");
    }
    // The installed 2.2.5 converter preserves Session.Message.ID as message.id
    // and admission metadata on the actual model-bound user message. Select
    // this request's last user, not the last submitted prompt for the session:
    // queued/parallel submissions must never supply an earlier turn's hint.
    const current = event.messages.findLast(message => message?.role === "user");
    const admissionID = current?.metadata?.[AUDIT_KEY]?.admission_id;
    const record = identity(current?.id) && typeof admissionID === "string" ?
      records.get(recordKey(event.sessionID, current.id, admissionID)) : undefined;
    const hint = modelHint(record, event.sessionID, current?.id);
    // Register only on primary `context`. Transient generate, summaries and
    // title generation have no admitted current user prompt and need no hint.
    event.system = event.system.filter(part => part?.metadata?.[AUDIT_KEY] !== VERSION);
    event.system.push({ type: "text", text: `<docatlas_language_preflight>\n${JSON.stringify(hint)}\n</docatlas_language_preflight>`,
      metadata: { [AUDIT_KEY]: VERSION } });
  };
  const dispose = () => {
    disposed = true;
    records.clear();
    for (const controller of pending) controller.abort(new DocumentationLanguagePreflightError(
      "documentation_language_preflight_unloaded"));
    pending.clear();
  };
  return { admit, inject, dispose };
}
