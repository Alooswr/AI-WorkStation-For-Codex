# Skill inventory and provenance boundary

## Source included

The following 18 Skill trees are materialized under `skills/`. Link-backed entries were copied from their canonical target and duplicates were removed.

- `banner-design`
- `design`
- `design-system`
- `easyeda-api`
- `embedded-daily-maintenance`
- `embedded-debug-verification`
- `embedded-project-closeout`
- `embedded-skill-router`
- `esp-idf-workflow`
- `hatch-pet`
- `jlc-eda-design`
- `keil-rebuild-debug`
- `lvgl-workflow`
- `mf-serial-hmi`
- `oh-story-codex`
- `playwright`
- `pua`
- `ux-writing`

Existing per-Skill license/NOTICE files and frontmatter license declarations are preserved. No top-level license attempts to relicense the collection.

## Inventory only

These local entries are deliberately not vendored because they are system/plugin managed, empty, duplicated, or their local redistribution status needs separate review:

- `brand`
- `codex-primary-runtime` (empty)
- `design-taste-frontend`
- `design-with-uiverse-animejs`
- `direct-product-design`
- `gpt-taste`
- `impeccable`
- `ui-styling` (local license metadata conflict)
- `ui-ux-pro-max`
- all `.codex/skills/.system` Skills
- all versioned `.codex/plugins/cache` Skills

Those entries should be restored through their original installer/plugin channel. See `managed-skills.txt` for the current machine's managed names and versions.

