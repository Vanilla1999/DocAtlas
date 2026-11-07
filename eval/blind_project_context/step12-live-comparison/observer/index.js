import { appendFileSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';

export default {
  id: 'docatlas-step12-observer',
  async setup(ctx) {
    const root = ctx.options.output;
    mkdirSync(root, { recursive: true });
    function save(type, event, data) {
      appendFileSync(join(root, 'events.jsonl'), JSON.stringify({
        type, time: new Date().toISOString(), sessionID: event.sessionID,
        kind: event.kind, model: event.model, data,
      }) + '\n');
    }
    for (const name of ['context', 'title', 'compaction', 'generate']) {
      await ctx.session.hook(name, e => save(name, e, {
        system: e.system, messages: e.messages, tools: e.tools, options: e.options,
      }));
    }
    for (const name of ['experimental.ws.send', 'experimental.ws.receive']) {
      await ctx.session.hook(name, e => save(name, e, e.frame));
    }
    await ctx.session.hook('http.request', async e => {
      save('http.request', e, await e.request.clone().text());
    });
    await ctx.session.hook('http.response', e => {
      const response = e.response.clone();
      void response.text().then(body => save('http.response', e, body))
        .catch(error => save('capture.error', e, String(error)));
    });
    await ctx.session.hook('retry', e => save('retry', e, {
      attempt: e.attempt, decision: e.decision, error: e.error,
    }));
  },
};
