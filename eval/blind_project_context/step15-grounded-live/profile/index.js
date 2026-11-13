// Scope guard only: original Grounded schemas, execution and results are unchanged.
export default {
  id: 'step15-grounded-readonly-profile',
  async setup(ctx) {
    const allowed = new Set(['grounded_search_docs', 'grounded_fetch_url']);
    const urls = new Set(ctx.options.urls);
    await ctx.mcp.transform(editor => {
      for (const [name] of editor.list()) if (name !== 'grounded') editor.remove(name);
    });
    await ctx.tool.transform(editor => {
      for (const tool of editor.list()) if (!allowed.has(tool.id)) editor.remove(tool.id);
    });
    for (const hook of ['context', 'generate', 'compaction']) {
      await ctx.session.hook(hook, event => {
        for (const name of Object.keys(event.tools)) if (!allowed.has(name)) delete event.tools[name];
      });
    }
    await ctx.session.hook('prompt', async event => {
      const start = performance.now();
      while (performance.now() - start < 10000) {
        const tools = await ctx.tool.list();
        if ([...allowed].every(id => tools.some(tool => tool.id === id))) {
          event.metadata = {...event.metadata, grounded_readiness: {status:'ready', required_tools:[...allowed]}};
          return;
        }
        await new Promise(resolve => setTimeout(resolve,25));
      }
      throw new Error('grounded_tools_not_ready');
    });
    await ctx.tool.hook('execute.before', event => {
      if (!allowed.has(event.tool)) throw new Error('grounded_readonly_boundary');
      const input = event.input;
      if (event.tool === 'grounded_search_docs' &&
          (input.library !== ctx.options.library || input.version !== ctx.options.version)) {
        throw new Error('grounded_library_version_boundary');
      }
      if (event.tool === 'grounded_fetch_url' && (!urls.has(input.url) || input.followRedirects !== false)) {
        throw new Error('grounded_exact_url_no_redirect_boundary');
      }
    });
    await ctx.session.hook('title', event => { event.result = 'Documentation'; });
  }
};
