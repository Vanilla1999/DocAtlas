from pathlib import Path

path = Path("docmancer/docs/interfaces/mcp/context_tools.py")
text = path.read_text(encoding="utf-8")
old = """                _annotate_recovery_handoff(
                projection,
                recovery,
                edit_authorized=source_search_edit_authorized,
            )
"""
new = """                _annotate_recovery_handoff(
                    projection,
                    recovery,
                    edit_authorized=source_search_edit_authorized,
                )
"""
count = text.count(old)
if count != 2:
    raise SystemExit(f"expected two formatting anchors, found {count}")
path.write_text(text.replace(old, new), encoding="utf-8")
print("source-handoff formatting normalized")
