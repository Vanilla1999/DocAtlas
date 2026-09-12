from pathlib import Path

path = Path("docmancer/core/_sqlite_store_active_fts.py")
text = path.read_text(encoding="utf-8")
old = '        conn.execute("DELETE FROM retrieval_children_fts")\n'
new = (
    '        conn.execute(\n'
    '            "INSERT INTO retrieval_children_fts(retrieval_children_fts) "\n'
    '            "VALUES (\\\'delete-all\\\')"\n'
    '        )\n'
)
if text.count(old) != 1:
    raise SystemExit(f"expected exactly one legacy projection clear, found {text.count(old)}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
