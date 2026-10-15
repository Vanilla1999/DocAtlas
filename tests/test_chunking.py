"""Tests for structure-aware markdown chunking."""
from docmancer.core.chunking import (
    chunk_text,
    chunk_paragraphs,
    chunk_markdown,
    _is_list_heavy,
    _fence_ranges,
    _parse_sections,
    _split_tables_and_code,
    _chunk_table_block,
    _chunk_code_block,
    _merge_small_chunks,
)

# ---------------------------------------------------------------------------
# Existing tests (preserved)
# ---------------------------------------------------------------------------

















# ---------------------------------------------------------------------------
# Table / code block sample data
# ---------------------------------------------------------------------------

SMALL_TABLE = """\
| Season | Start       | End           |
|--------|-------------|---------------|
| 1      | Oct 28 2024 | Feb 28 2025   |
| 2      | Mar 1 2025  | Jun 2 2025    |
| 5      | Dec 9 2025  | Mar 9 2026    |
"""

LARGE_TABLE_HEADER = "| Source         | Adapter        | DB / Format              | Status     |"
LARGE_TABLE_SEP    = "|----------------|----------------|--------------------------|------------|"
LARGE_TABLE_ROWS   = [
    "| iMessage       | imessage.ts    | SQLite chat.db           | Production |",
    "| WhatsApp       | whatsapp.ts    | SQLite ChatStorage.sqlite | New       |",
    "| Apple Notes    | notes.ts       | SQLite NoteStore.sqlite  | New        |",
    "| Apple Contacts | contacts.ts    | AddressBook / vCard      | New        |",
    "| macOS Stickies | stickies.ts    | Stickies DB / plist      | New        |",
    "| Apple Reminders| reminders.ts   | SQLite                   | New        |",
    "| Screenshots    | screenshots.ts | Metadata + optional OCR  | New        |",
]

# ---------------------------------------------------------------------------
# _split_tables_and_code
# ---------------------------------------------------------------------------











# ---------------------------------------------------------------------------
# _chunk_table_block
# ---------------------------------------------------------------------------









# ---------------------------------------------------------------------------
# _chunk_code_block
# ---------------------------------------------------------------------------









# ---------------------------------------------------------------------------
# chunk_markdown with tables
# ---------------------------------------------------------------------------







# ---------------------------------------------------------------------------
# List-heavy section regression
# ---------------------------------------------------------------------------





# ---------------------------------------------------------------------------
# Fence-aware header parsing regression
# ---------------------------------------------------------------------------
