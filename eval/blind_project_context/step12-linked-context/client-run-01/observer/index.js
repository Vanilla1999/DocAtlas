import { appendFileSync } from "node:fs";
export default { id: "docatlas-client-acceptance-observer", async setup(ctx) {
  await ctx.session.hook("title", event => { event.result = "Documentation"; });
  await ctx.session.hook("prompt", event => { appendFileSync(new URL("../client-prompts.jsonl", import.meta.url), JSON.stringify({location:ctx.location.directory,metadata:event.metadata}) + "\n"); });
  await ctx.session.hook("context", event => { appendFileSync(new URL("../client-rendered-results.jsonl", import.meta.url), JSON.stringify({location:ctx.location.directory,messages:event.messages.filter(m=>m.role==="tool")}) + "\n"); });
  await ctx.tool.hook("execute.after", event => { appendFileSync(new URL("../client-tools.jsonl", import.meta.url), JSON.stringify(event) + "\n"); });
} };
