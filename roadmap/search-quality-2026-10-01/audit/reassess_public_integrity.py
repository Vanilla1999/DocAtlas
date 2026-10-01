"""Correct public integrity observer only; no new calls or answer scoring."""
import json
from run_live_mcp import OUT, WORK, ROOT, save, verify_sources


def main():
    result={}
    for panel in ('project80','external80'):
        rows=json.loads((OUT/'raw'/panel/'results.json').read_text())
        corrected=[]
        for row in rows:
            root=ROOT if panel=='project80' else WORK/'fixtures'/row['project']
            corrected.append(dict(id=row['id'],lane=row.get('lane','native'),
                errors=verify_sources(row['payload'],root),
                original_false_file_hash_errors=row['integrity_errors']))
        result[panel]=dict(rows=len(rows),violations=sum(bool(r['errors']) for r in corrected),rows_detail=corrected)
    save(OUT/'raw/public-integrity-corrected.json',dict(
        correction='Initial observer incorrectly treated content_sha256 as raw file SHA256. Production hashes canonical evidence material. Original raw results retained unchanged. Corrected public checks verify digest shape, file scope, verbatim bytes and line spans. Full snapshot binding is assessed separately on observed trace calls.',
        panels=result))
    print({k:{a:b for a,b in v.items() if a!='rows_detail'} for k,v in result.items()})


if __name__=='__main__':
    main()
