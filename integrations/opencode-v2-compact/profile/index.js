import { lstat, readFile, readdir, realpath } from "node:fs/promises";
import { createHash } from "node:crypto";
import path from "node:path";

class DocumentationReadinessError extends Error {
  constructor(checks, reason = "documentation_profile_mcp_not_ready") {
    super(`${reason}: required context/status tools unavailable after ${checks} catalog checks`);
    this.name = "DocumentationReadinessError";
    this.code = reason;
  }
}

// This plugin is for an explicitly created read-only documentation location.
// It is not a replacement for project instructions or an operating-system sandbox.
export default {
  id: "docatlas-documentation-light-v1",
  async setup(ctx) {
    const { backend, projectRoot, serverName = "docatlas" } = ctx.options;
    if (!["mcp", "files"].includes(backend) || typeof projectRoot !== "string" ||
        !path.isAbsolute(projectRoot) || !/^[A-Za-z][A-Za-z0-9_]*$/.test(serverName)) {
      throw new Error("Documentation profile requires a backend, absolute root and explicit server name");
    }
    const root = await realpath(projectRoot);
    if (root !== projectRoot) throw new Error("Documentation profile root changed; regenerate the profile");
    const prefix = root + path.sep;
    const contextTool = `${serverName}_get_docs_context`;
    const statusTool = `${serverName}_docs_status`;
    const sourceTool = `${serverName}_read_docs_source`;
    const resourceTool = "opencode_read_mcp_resource";
    const allowed = new Set(backend === "mcp" ?
      [contextTool, statusTool, sourceTool, resourceTool] : ["read", "glob", "grep"]);
    const lifecycle = new AbortController();
    const frozen = ctx.options.fileSnapshot;
    if (backend === "files" && (!Array.isArray(frozen) || !frozen.length || frozen.some(row =>
        typeof row.path !== "string" || path.isAbsolute(row.path) || row.path.split("/").includes("..") ||
        !/^[0-9a-f]{64}$/.test(row.sha256)))) {
      throw new Error("Files control requires a verified isolated source manifest");
    }
    const verifyFiles = async () => {
      if (backend !== "files") return;
      const expected = new Map(frozen.map(row => [row.path, row.sha256]));
      if (expected.size !== frozen.length) throw new Error("Invalid files control manifest");
      const seen = new Set();
      const walk = async directory => {
        for (const name of await readdir(directory)) {
          const target = path.join(directory, name);
          const stat = await lstat(target);
          if (stat.isSymbolicLink()) throw new Error("documentation_profile_source_changed");
          if (stat.isDirectory()) await walk(target);
          else if (stat.isFile()) {
            const relative = path.relative(root, target).split(path.sep).join("/");
            const digest = createHash("sha256").update(await readFile(target)).digest("hex");
            if (expected.get(relative) !== digest) throw new Error("documentation_profile_source_changed");
            seen.add(relative);
          } else throw new Error("documentation_profile_source_changed");
        }
      };
      await walk(root);
      if (seen.size !== expected.size) throw new Error("documentation_profile_source_changed");
    };
    await verifyFiles();

    // Configuration and native registry filtering is useful, but V2.2.5 can
    // attach MCP tools after these transforms. Runtime hooks below enforce the
    // same boundary on the final tool set and on every actual call.
    await ctx.mcp.transform(editor => {
      for (const [name] of editor.list()) {
        if (backend !== "mcp" || name !== serverName) editor.remove(name);
      }
    });
    if (backend === "mcp") await ctx.session.hook("prompt", async event => {
      // MCP's connected notification can precede native tool publication in
      // V2.2.5. Prompt admission runs before the executable model-tool snapshot.
      // Wait for the actual public registry condition, never a guessed delay.
      const started = performance.now();
      const deadline = started + 10000;
      let checks = 0;
      while (!lifecycle.signal.aborted) {
        const tools = await ctx.tool.list();
        checks += 1;
        if ([contextTool, statusTool].every(id => tools.some(tool => tool.id === id))) {
          event.metadata = { ...event.metadata, docatlas_readiness: {
            status: "ready", checks, elapsed_ms: Math.round(performance.now() - started),
            deadline_ms: 10000, required_tools: [contextTool, statusTool],
          } };
          return;
        }
        const remaining = deadline - performance.now();
        if (remaining <= 0) throw new DocumentationReadinessError(checks);
        await new Promise(resolve => setTimeout(resolve, Math.min(25, remaining)));
      }
      throw new DocumentationReadinessError(checks, "documentation_profile_unloaded");
    });
    const localPath = async value => {
      if (typeof value !== "string" || !value) throw new Error("A source path is required");
      const candidate = path.resolve(root, value);
      if (candidate !== root && !candidate.startsWith(prefix)) {
        throw new Error("documentation_profile_scope_mismatch");
      }
      const resolved = await realpath(candidate);
      if (resolved !== root && !resolved.startsWith(prefix)) {
        throw new Error("documentation_profile_scope_mismatch");
      }
      return resolved;
    };
    const projectArgs = async input => {
      if (input.project_path && await localPath(input.project_path) !== root) {
        throw new Error("documentation_profile_target_mismatch");
      }
      if (input.library || input.libraries || input.canonical_id || input.module || input.module_path ||
          input.scope && input.scope !== "project" || input.mode && !["auto", "project"].includes(input.mode)) {
        throw new Error("documentation_profile_scope_mismatch");
      }
    };
    await ctx.tool.hook("execute.before", async event => {
      if (!allowed.has(event.tool)) throw new Error("documentation_profile_read_only");
      if (backend !== "mcp") return;
      const input = event.input;
      if (event.tool === contextTool) {
        await projectArgs(input);
        if (input.context_format !== undefined && input.context_format !== null) {
          throw new Error("documentation_profile_read_only");
        }
        event.input = { ...input, scope: "project" };
      } else if (event.tool === statusTool) {
        await projectArgs(input);
        if (input.action && input.action !== "project" || input.job_id) {
          throw new Error("documentation_profile_project_status_only");
        }
        event.input = { ...input, action: "project" };
      } else if (event.tool === resourceTool) {
        if (input.server !== serverName || typeof input.uri !== "string" ||
            !input.uri.startsWith("docatlas://source/")) {
          throw new Error("documentation_profile_source_uri_required");
        }
      }
    });
    const visibleTools = event => {
      for (const name of Object.keys(event.tools)) {
        if (!allowed.has(name)) delete event.tools[name];
      }
    };
    for (const hook of ["context", "generate", "compaction"]) {
      await ctx.session.hook(hook, visibleTools);
    }
    await ctx.tool.transform(editor => {
      for (const tool of editor.list()) {
        if (!allowed.has(tool.id)) editor.remove(tool.id);
      }
      for (const id of allowed) editor.update(id, tool => {
        const execute = tool.execute;
        tool.options = { ...tool.options, codemode: false };
        tool.execute = async (input, context) => {
          if (backend === "files") {
            await verifyFiles();
            // V2's current native read uses path. A client exposing the older
            // filePath spelling is kept within the same bound root too; never
            // leave an unchecked second path for the executor to prefer.
            if (id === "read" && input.path !== undefined && input.filePath !== undefined &&
                input.path !== input.filePath) throw new Error("documentation_profile_ambiguous_read_path");
            const key = id === "read" && input.filePath !== undefined ? "filePath" : "path";
            const value = input[key] ?? (id === "read" ? null : root);
            input = { ...input, [key]: await localPath(value) };
            if (id === "read" && input.path !== undefined && input.filePath !== undefined) {
              input.path = input.filePath = input[key];
            }
            // Search syntax may match names under the root, not traverse to a
            // parent or turn the requested pattern into a second absolute root.
            for (const pattern of [id === "glob" ? input.pattern : input.include]) {
              if (typeof pattern === "string" && (path.isAbsolute(pattern) || pattern.includes(".."))) {
                throw new Error("documentation_profile_scope_mismatch");
              }
            }
          }
          const result = await execute(input, context);
          // A frozen control cannot publish a read if its source set changed
          // during native execution. This is a diagnostic snapshot guard, not
          // replacement of the file tool or the MCP server's live checks.
          if (backend === "files") await verifyFiles();
          return result;
        };
      });
    });
    // Both comparison arms use the same deterministic title, not an extra
    // provider call. No user question, system instruction or history is rewritten.
    await ctx.session.hook("title", event => { event.result = "Documentation"; });
    return () => lifecycle.abort();
  },
};
