export default { id: "question-audit-title", async setup(ctx) { await ctx.session.hook("title", e => { e.result = "Question transport audit"; }); } };
