from pathlib import Path

p = Path("scripts/run_agent_developer_gate.py")
text = p.read_text(encoding="utf-8")
old = "from scripts.agent_developer_gate_support import apply_agent_protocol_extensions\n"
new = (
    "if __package__:\n"
    "    from .agent_developer_gate_support import apply_agent_protocol_extensions\n"
    "else:\n"
    "    from agent_developer_gate_support import apply_agent_protocol_extensions\n"
)
if text.count(old) == 1:
    text = text.replace(old, new, 1)
elif new not in text:
    raise RuntimeError("unexpected agent gate support import")
p.write_text(text, encoding="utf-8")
