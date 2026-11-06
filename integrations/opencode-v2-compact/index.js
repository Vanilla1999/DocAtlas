import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

const counter = fileURLToPath(new URL("./count_tokens.py", import.meta.url));

function counts(python, texts, signal) {
  return new Promise((resolve, reject) => {
    const child = spawn(python, [counter], { stdio: ["pipe", "pipe", "pipe"], signal });
    let stdout = "";
    let stderr = "";
    child.stdout.setEncoding("utf8").on("data", data => { stdout += data; });
    child.stderr.setEncoding("utf8").on("data", data => { stderr += data; });
    child.on("error", reject);
    child.stdin.on("error", reject);
    child.on("close", code => {
      if (code !== 0) return reject(new Error(`Offline tokenizer failed (${code}): ${stderr}`));
      try {
        const result = JSON.parse(stdout);
        if (!Number.isSafeInteger(result.emergency_tokens) || result.emergency_tokens <= 0 ||
            !Array.isArray(result.counts) || result.counts.length !== texts.length ||
            result.counts.some(n => !Number.isSafeInteger(n) || n < 0)) throw new Error("Invalid host contract/counts");
        resolve(result);
      } catch (error) { reject(error); }
    });
    child.stdin.end(JSON.stringify(texts));
  });
}

function stop(limit, reason, measured) {
  return JSON.stringify({ kind: "docs_context_error", reason_code: reason,
    boundary: "opencode_model_visible", token_limit: limit,
    ...(measured === undefined ? {} : { measured_tokens: measured }),
    delivered: false, next_portion: null });
}

// Keep the authoritative content, including error/continuation fields, byte for
// byte. Do not infer evidence from hidden output/metadata or parse/repack sources.
function textContent(content) {
  if (typeof content === "string") return content;
  if (Array.isArray(content) && content.length === 1 && content[0].type === "text") {
    return content[0].text;
  }
  throw new Error("Compact adapter requires one self-contained text result");
}

// V2 plugins accept an id/setup export directly; no V1 hooks or SDK dependency.
export default {
  id: "docatlas-compact-v2",
  async setup(ctx) {
    const tools = ctx.options.tools;
    const python = ctx.options.python;
    if (!Array.isArray(tools) || !tools.length || tools.some(t => typeof t !== "string") ||
        typeof python !== "string" || !python.startsWith("/")) {
      throw new Error("Set explicit effective tool IDs and an absolute installed DocAtlas Python executable");
    }
    // Read the sole host contract from the installed candidate, never options or
    // agent input. Old packages missing that contract fail activation explicitly.
    const { emergency_tokens: limit } = await counts(python, []);
    const count = async (texts, signal) => {
      const result = await counts(python, texts, signal);
      if (result.emergency_tokens !== limit) throw new Error("Host contract changed; reload adapter");
      return result.counts;
    };
    const names = new Set(tools);
    await ctx.tool.transform(editor => {
      for (const name of names) editor.update(name, tool => {
        const execute = tool.execute;
        tool.options = { ...tool.options, codemode: false };
        tool.execute = async (input, context) => {
          const result = await execute(input, context);
          let text;
          try {
            text = textContent(result.content);
            const [size] = await count([text], context.signal);
            if (size > limit) text = stop(limit, "context_emergency_stop", size);
          } catch (error) {
            if (context.signal.aborted) throw error;
            text = stop(limit, "client_envelope_unverified");
          }
          // Native tools deliver content, not the structured output a Code Mode
          // caller may re-expand. Do not retain a second large body in output.
          return { ...result, output: text, content: [{ type: "text", text }] };
        };
      });
    });
    // Reprice AFTER OpenCode's tool rendering, for every model-bound flow.
    // A later plugin can still change these messages: install this plugin last.
    const guard = async event => {
      const results = event.messages.flatMap(message => message.role === "tool" ? message.content : [])
        .filter(part => part.type === "tool-result" && names.has(part.name));
      if (!results.length) return;
      const texts = results.map(part => part.result.type === "text" ? part.result.value : "");
      let sizes;
      try { sizes = await count(texts); }
      catch { sizes = texts.map(() => undefined); }
      results.forEach((part, index) => {
        const size = sizes[index];
        // v2.2.5 truncation is applied after execution; never send its hidden-file
        // placeholder as if it were the documentation evidence.
        const truncated = texts[index].includes("full output saved to ") &&
          (texts[index].startsWith("[showing ") || texts[index].includes("\n[showing "));
        if (part.result.type !== "text" || size === undefined || size > limit || truncated) {
          part.result = { type: "text", value: stop(limit, size > limit ?
            "context_emergency_stop" : truncated ? "client_output_truncated" : "client_envelope_unverified", size) };
        }
      });
    };
    for (const hook of ["context", "compaction", "generate", "title"]) {
      await ctx.session.hook(hook, guard);
    }
  },
};
