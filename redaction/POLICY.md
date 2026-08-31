# Redaction policy

This snapshot is safe by selection first and replacement second.

## Never copied

- live or backup Codex configuration;
- auth/API/OAuth/key material and secret directories;
- raw memory databases, raw full memory index, sessions, history and logs;
- browser/Computer Use state, native pipes and installation identifiers;
- actual device configuration, project source, build artifacts and local mapping files;
- managed runtime/plugin caches and dependency caches.

## Normalized

- personal name to a neutral owner placeholder;
- user home paths to `%USERPROFILE%` or repository placeholders;
- GitHub owner and remote infrastructure identifiers to placeholders;
- organization/product-specific archive naming to parameterized fields;
- memory content to an independently written, general-purpose digest.

## Review gates

1. Run `python scripts/audit_redaction.py .`.
2. Review every path under `inventory/` and `config/`.
3. Confirm `git status --short` contains only intended files.
4. Inspect `git diff --cached --stat` and a name-only list before committing.
5. Push only to a repository whose visibility was confirmed as `PRIVATE`.

The private mapping from placeholders to real machine values must never be committed.

