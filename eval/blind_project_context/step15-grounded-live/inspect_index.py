"""Read-only preservation after preparation configuration mismatch."""
import hashlib, json, pathlib, sqlite3
HERE=pathlib.Path(__file__).resolve().parent
DB=pathlib.Path('/home/viadmin/.local/share/docs-mcp-server/documents.db')
c=sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True)
c.row_factory=sqlite3.Row
sources=json.loads((HERE/'sources.json').read_text())
pages=[dict(r) for r in c.execute('SELECT p.* FROM pages p JOIN versions v ON p.version_id=v.id JOIN libraries l ON v.library_id=l.id WHERE l.name=? AND v.name=?',('meridian-step15-e62fa9e3','1.0.0'))]
for p in pages:
    p['chunks']=[dict(r) for r in c.execute('SELECT id,content,metadata,sort_order,length(embedding) AS embedding_bytes FROM documents WHERE page_id=? ORDER BY sort_order',(p['id'],))]
    original=next((s for s in sources if s['url'].removesuffix('.md')==p['url']),None)
    p['source']=original
    if original:
        text=(HERE/'source-bytes'/original['path']).read_text()
        for ch in p['chunks']:
            content=ch['content']; pos=text.find(content)
            ch['sha256']=hashlib.sha256(content.encode()).hexdigest()
            ch['exact_source_substring']=pos>=0
            ch['source_line_span']=([text[:pos].count('\n')+1,text[:pos+len(content)].count('\n')+1] if pos>=0 else None)
result={'database':str(DB),'library':'meridian-step15-e62fa9e3','version':'1.0.0','pages':pages,'page_count':len(pages),'all_pages_allowlisted':len(pages)==6 and all(p['source'] for p in pages),'boundary':'Read-only index inspection, not semantic grading. Raw URLs are normalized by Grounded with .md removed; original source URL is preserved separately.'}
with (HERE/'index-inspection.json').open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2)
print(json.dumps({'pages':len(pages),'chunks':sum(len(p['chunks']) for p in pages),'all_allowlisted':result['all_pages_allowlisted'],'exact_chunks':sum(ch['exact_source_substring'] for p in pages for ch in p['chunks'])}))
