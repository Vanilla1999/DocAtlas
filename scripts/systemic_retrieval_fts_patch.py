from pathlib import Path

projection = Path("docmancer/core/_sqlite_store_active_fts.py")
text = projection.read_text(encoding="utf-8")
old = '        conn.execute("DELETE FROM retrieval_children_fts")\n'
new = (
    '        conn.execute(\n'
    '            "INSERT INTO retrieval_children_fts(retrieval_children_fts) "\n'
    '            "VALUES (\\\'delete-all\\\')"\n'
    '        )\n'
)
if text.count(old) != 1:
    raise SystemExit(f"expected exactly one legacy projection clear, found {text.count(old)}")
projection.write_text(text.replace(old, new, 1), encoding="utf-8")

part02 = Path("docmancer/core/_sqlite_store_part02.py")
text = part02.read_text(encoding="utf-8")
superseded_cleanup = '''                child_ids = [
                    int(item["id"])
                    for item in conn.execute(
                        "SELECT id FROM retrieval_children WHERE generation_id = ?",
                        (generation_id,),
                    )
                ]
                for child_id in child_ids:
                    conn.execute(
                        "DELETE FROM retrieval_children_fts WHERE rowid = ?", (child_id,)
                    )
'''
discard_cleanup = '''            child_ids = [int(row["id"]) for row in conn.execute(
                "SELECT id FROM retrieval_children WHERE generation_id = ?", (generation_id,)
            )]
            for child_id in child_ids:
                conn.execute("DELETE FROM retrieval_children_fts WHERE rowid = ?", (child_id,))
'''
for block, indent in ((superseded_cleanup, "                "), (discard_cleanup, "            ")):
    if text.count(block) != 1:
        raise SystemExit("expected one generation-local FTS cleanup block")
    text = text.replace(
        block,
        indent + "# FTS5 is an active-generation projection. Inactive/candidate\n"
        + indent + "# backing rows have no postings to delete here.\n",
        1,
    )
part02.write_text(text, encoding="utf-8")
