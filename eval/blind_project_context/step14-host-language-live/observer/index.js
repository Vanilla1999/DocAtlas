import { appendFileSync, existsSync, mkdirSync, renameSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

// Native V2 hooks, as in Step12. Never record URLs, headers or environment.
// Bun hrtime is process-relative: never compare it to Python monotonic_ns.
// Cross-process ordering uses wall-v2 epoch clocks, with millisecond precision.
export default {
  id: 'docatlas-step14-live-observer',
  async setup(ctx) {
    const root = ctx.options.output;
    mkdirSync(root, { recursive: true });
    // The authorized work path is below the real user's home. V2 can discover
    // ancestor skills there even with an isolated HOME/XDG config. This common
    // experimental control removes that ambient catalog in every arm.
    await ctx.skill.transform(editor => { for (const skill of editor.list()) editor.remove(skill.id); });
    const pending = new Set();
    const state = { requests: 0, completed: 0, usage_ids: [], capture_errors: 0 };
    function checkpoint() {
      writeFileSync(join(root, 'state.tmp'), JSON.stringify(state));
      renameSync(join(root, 'state.tmp'), join(root, 'state.json'));
    }
    checkpoint();
    function responseCompleted(e, body) {
      const records = [];
      function scan(value) {
        if (!value || typeof value !== 'object') return;
        if (value.id && typeof value.usage?.input_tokens === 'number') records.push(value);
        for (const child of Object.values(value)) scan(child);
      }
      try { scan(JSON.parse(body)); } catch {
        for (const line of body.split('\n')) {
          if (line.startsWith('data: ')) {
            try { scan(JSON.parse(line.slice(6))); } catch { /* SSE heartbeat/[DONE] */ }
          }
        }
      }
      state.completed += 1;
      state.usage_ids = [...new Set([...state.usage_ids, ...records.map(r => r.id)])];
      save('capture.response.completed', e, { usage_ids: records.map(r => r.id) });
      checkpoint();
    }
    let first = true;
    function save(type, e, data, ns = process.hrtime.bigint().toString(), wall = Date.now()) {
      appendFileSync(join(root, 'events.jsonl'), JSON.stringify({ type,
        monotonic_ns: ns, wall_time_ms: wall, capture_version: 'wall-v2',
        time: new Date(wall).toISOString(), sessionID: e.sessionID,
        kind: e.kind, model: e.model, data }) + '\n');
    }
    function guard() {
      if (existsSync(ctx.options.fatal)) throw new Error('step14_fatal_stop_no_retry');
    }
    function request(type, e, body, ns, wall = Date.now()) {
      guard();
      save(type, e, body, ns, wall);
      state.requests += 1;
      checkpoint();
      if (first) {
        writeFileSync(join(root, 'first-provider-request.json'), JSON.stringify({
          type, monotonic_ns: ns, wall_time_ms: wall, capture_version: 'wall-v2',
          sessionID: e.sessionID, kind: e.kind, model: e.model, body,
          boundary: 'native pre-dispatch hook, not a remote receipt; no headers captured',
        }, null, 2), { flag: 'wx' });
        first = false;
      }
    }
    await ctx.session.hook('prompt', e => save('prompt.admitted', e, { metadata: e.metadata }));
    for (const name of ['context', 'title', 'compaction', 'generate']) {
      await ctx.session.hook(name, e => {
        guard();
        save(name, e, { system: e.system, messages: e.messages, tools: e.tools, options: e.options });
      });
    }
    await ctx.session.hook('experimental.ws.send', e => request('experimental.ws.send', e, e.frame, process.hrtime.bigint().toString()));
    await ctx.session.hook('experimental.ws.receive', e => {
      save('experimental.ws.receive', e, e.frame);
      try {
        if (JSON.parse(e.frame).type === 'response.completed') responseCompleted(e, e.frame);
      } catch { /* retain original frame and let native provider classify it */ }
    });
    await ctx.session.hook('http.request', async e => {
      const ns = process.hrtime.bigint().toString();
      const wall = Date.now();
      request('http.request', e, await e.request.clone().text(), ns, wall);
    });
    await ctx.session.hook('http.response', e => {
      const ns = process.hrtime.bigint().toString();
      const task = e.response.clone().text().then(body => {
        save('http.response', e, { status: e.response.status, body }, ns);
        responseCompleted(e, body);
      }).catch(error => {
        state.capture_errors += 1;
        save('capture.error', e, { name: error.name });
        checkpoint();
      });
      pending.add(task);
      void task.finally(() => pending.delete(task));
    });
    await ctx.session.hook('retry', e => {
      save('retry', e, { attempt: e.attempt, proposed: e.decision,
        error: { type: e.error.type, status: e.error.status } });
      e.decision = { retry: false };
    });
    await ctx.tool.hook('execute.before', e => { guard(); save('tool.before', e, e); });
    await ctx.tool.hook('execute.after', e => save('tool.after', e, e));
    return async () => { await Promise.allSettled([...pending]); };
  },
};
