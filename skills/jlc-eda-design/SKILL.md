---
name: jlc-eda-design
description: Design, create, modify, inspect, and validate schematics and PCBs in 嘉立创EDA专业版 through the official EasyEDA API bridge. Use for 嘉立创EDA/EasyEDA schematic capture, PCB layout, component and footprint work, ERC/DRC, or controlled edits to an existing EDA project. Do not use for 嘉立创EDA标准版 or unrelated mechanical CAD.
---

# 嘉立创 EDA 设计

Use the official `easyeda-api` skill as the API and transport layer. This skill adds a Windows-ready bridge workflow plus engineering gates for safe, reviewable EDA design.

## Load only what the task needs

- On first use in a task, read the sibling `../easyeda-api/SKILL.md` completely. Use its `references/` files as the source of truth for every API signature, enum, interface, and coordinate unit.
- Read [references/setup.md](references/setup.md) when the bridge, Gateway extension, permissions, or connection is missing or unhealthy.
- Read [references/design-workflow.md](references/design-workflow.md) before creating or materially changing a schematic or PCB.
- Read [references/schematic-engineering-standard.md](references/schematic-engineering-standard.md) before creating, materially reviewing, or releasing a schematic. Treat it as the canonical electrical and documentation review gate; do not replace it with visual imitation of a reference design.
- Read [references/pcb-engineering-standard.md](references/pcb-engineering-standard.md) before placing, routing, materially reviewing, or releasing a PCB. Treat its pre-route placement gate and rendered-board review as mandatory.

If `../easyeda-api` is missing, stop and report the missing dependency. Do not replace precise EDA operations with guessed canvas clicks.

## Choose the control surface

- Use the official API bridge for project, document, schematic, PCB, library, save, ERC, and DRC operations.
- Use Computer Use only to open 嘉立创EDA专业版, manage or reconnect the Gateway extension, and visually inspect the rendered result. Do not draw precise geometry by mouse when the API can express it.
- Edit `.eprj3` source directly only when the user explicitly requests file-level work and a recoverable copy exists.

## Protect the user's designs

- Before any write, verify bridge identity, connected window, current project, current document, and document type.
- Lock the target as `windowId + projectUuid + documentUuid + documentType`. Re-read and compare the lock before every write batch; stop if any field changes.
- Treat the open project as user data. Never overwrite, replace, or switch away from it on an assumption. `openProject` can discard unsaved work; use it only after the target is explicit and the current work is saved or recoverable.
- For a new design, create a new project or user-designated copy. For an existing design, inventory it read-only first and keep changes narrowly within the request.
- Do not automate the Gateway's external-interaction permission prompt. Pause for the user to approve that permission in 嘉立创EDA.
- The bridge executes local JavaScript without an authentication token. Bind and access it only on `127.0.0.1`, use it on a trusted workstation, start it only for an active EDA task, and stop it at task end unless the user explicitly asks to keep it running.

## Connect and inspect

1. Run `scripts/bridge.ps1 -Action start` from this skill directory. It verifies the service identity before reusing any port.
2. Check `/health` and require `service == "easyeda-bridge"` and `edaConnected == true`.
3. Check `/eda-windows`. Auto-select only when exactly one window is connected; ask the user when multiple windows exist.
4. Read current project and document info before selecting any write API.

Do not call an undocumented method, guess an enum, or infer a parameter order. Read the exact class reference and remarks first, `await` promise-returning methods, and return results explicitly from bridge code.

## Execute design work

- For a new design or a change to electrical behavior, parts, packages, pins, or nets, turn the request into explicit sheets or functional blocks, exact parts, net names, voltage domains, interfaces, board constraints, and acceptance checks. Resolve electrical decisions from the exact device datasheet and errata first, then the vendor hardware guide and reference design. Keep general drawing conventions subordinate to device-specific evidence.
- For a metadata-only edit, inspect the target read-only, disambiguate only the requested field, change only that field, read it back, and perform a local visual check. Do not demand a full design contract or device-evidence cards unless the edit can alter connectivity, BOM identity, pin mapping, or electrical meaning.
- When selecting or replacing a part, prefer exact LCSC part IDs and verified symbols/footprints. Do not silently substitute a different electrical part or package.
- Apply changes in small coherent batches. After each batch, read back the affected primitives and validate counts, IDs, coordinates, attributes, pin mapping, and nets before continuing.
- Record the IDs created or changed by each batch. On a partial failure, retry only missing items; do not replay the full batch and create duplicates.
- Remember the unit split: schematic coordinates use `0.01 inch`; PCB coordinates use `1 mil`.
- A placed component is not proof of connectivity. Verify wires/net labels, power pins, no-connect intent, symbol-to-footprint mapping, and the generated net relationships.
- Do not substitute a bidirectional, input, or output port for an ordinary same-sheet net label merely because the current API version lacks a net-label method. Use the EDA UI through Computer Use for that specific placement, or use a clear physical wire; preserve port symbols for genuine sheet or hierarchy boundaries and use their real direction.
- Save at stable checkpoints. Run the relevant ERC/DRC, then inspect the rendered schematic or PCB visually for overlaps, unreadable labels, off-sheet objects, poor grouping, and implausible placement. Do not start PCB routing until the placement-only visual gate passes.

## Completion evidence

Report these gates separately:

- requested design change implemented;
- API readback matched the intended objects and nets;
- save succeeded;
- ERC/DRC result and any accepted exceptions;
- visual inspection result;
- exports or manufacturing outputs, if requested.

Never report an API success as electrical correctness, visual acceptance, or manufacturing readiness without the corresponding evidence.

At task end, run `scripts/bridge.ps1 -Action stop` unless the user explicitly requested that the bridge remain available.
