"""One-time reviewed integration patch; no runtime selection changes elsewhere."""
from pathlib import Path
p = Path('docmancer/docs/interfaces/mcp/context_tools.py')
s = p.read_text()
old = '            section_compression_active = False\n'
new = '''            if kind == "docs_context":
                from docmancer.docs.application.answerability import apply_answerability
                projection, snapshot = apply_answerability(projection, snapshot, raw, question)
            section_compression_active = False
'''
assert s.count(old) == 1
p.write_text(s.replace(old, new))
