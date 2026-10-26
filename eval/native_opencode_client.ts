// Runs INSIDE pinned OpenCode v2.1.2. Real MCP and ToolOutput, no model calls.
import fs from "node:fs/promises"
import path from "node:path"
import assert from "node:assert/strict"
import { Effect } from "effect"
import { AppNodeBuilder } from "@opencode/core/effect/app-node-builder"
import { LayerNode } from "@opencode/util/effect/layer-node"
import { ToolOutput } from "@opencode/core/tool-output"
import { FSUtil } from "@opencode/util/fs-util"
import { Global } from "@opencode/util/global"
import { McpClient } from "@opencode/core/mcp/client"
import { hostEnvironmentLayer } from "./fixture/environment"

const protocol=JSON.parse(await fs.readFile(process.env.DOCATLAS_PROTOCOL!,"utf8"))
const results:any[]=[]
const outputLayer=AppNodeBuilder.build(LayerNode.group([ToolOutput.node,FSUtil.node]),[
  Global.node.replace(Global.layerWith({data:path.join(protocol.out,"opencode-data")})),
])
const work=Effect.gen(function*(){
  const output=yield* ToolOutput.Service
  for(const arm of ["delivery-only","guarded"]){
    const environment={...protocol.registration.environment,
      DOCATLAS_CONTEXT_COMPRESSION:"off",DOCATLAS_MCP_PRESENTATION:"opencode-v1",
      ...(arm==="delivery-only"?{DOCATLAS_NATIVE_SELECTION:"preserve"}:{})}
    const connection=yield* McpClient.connect("docatlas",{type:"local",
      command:[protocol.cli,"mcp","docs-serve"],environment},protocol.root)
    const tools=yield* connection.tools()
    assert(tools.some(t=>t.name==="get_docs_context"))
    for(const item of protocol.cases){
      const reply=yield* connection.callTool({name:"get_docs_context",args:{
        question:item.question,project_path:protocol.root,scope:"project"}})
      assert(!reply.isError)
      const text=reply.content.filter(c=>c.type==="text").map(c=>(c as any).text).join("\n")
      const normalized=yield* output.truncate({content:[{type:"text",text}]})
      const visible=normalized.content.filter(c=>c.type==="text").map(c=>(c as any).text).join("\n")
      const row={arm,id:item.id,raw_bytes:Buffer.byteLength(text),truncated:normalized.metadata?.truncated===true,
                 output_path:normalized.metadata?.outputPath??null,model_visible_text:visible,
                 meta_retained:"_meta" in reply,structured_retained:reply.structured!==undefined}
      results.push(row)
      assert.equal(row.truncated,false,item.id)
      assert.equal(row.output_path,null)
      assert.equal(row.meta_retained,false)
      assert.equal(row.structured_retained,false)
      assert.equal(visible,text)
      assert(!visible.includes('"content_sha256"')&&!visible.includes('"source_uri"'))
    }
  }
})
await Effect.runPromise(Effect.scoped(work).pipe(Effect.provide(hostEnvironmentLayer),Effect.provide(outputLayer)))
await fs.writeFile(path.join(protocol.out,"OPENCODE.json"),JSON.stringify({version:"2.1.2",
  source_commit:"a517687fde98a7329ada3ae644a01a9fc6c4e99e",model_calls:0,tool_calls:results.length,results},null,2))
console.log(JSON.stringify({calls:results.length,native_truncations:results.filter(r=>r.truncated).length}))
