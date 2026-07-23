# memory/

Runtime data for the local-first Memory module (ADR-0004) — the actual
SQLite database file(s) and local embedding index once
SQLiteMemoryStore is wired up.

This is NOT src/master_agent/memory/ — that package holds the code
(the MemoryStore interface and its SQLite implementation). This folder
holds the data that code reads and writes. Kept out of git — see
.gitignore.
