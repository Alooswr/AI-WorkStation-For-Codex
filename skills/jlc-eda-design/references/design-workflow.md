# 原理图与 PCB 工作流

Read this reference before creating or materially changing a 嘉立创EDA design.

For any schematic creation, material review, or release decision, also read [schematic-engineering-standard.md](schematic-engineering-standard.md). For any PCB placement, routing, material review, or release decision, also read [pcb-engineering-standard.md](pcb-engineering-standard.md). Those files are the canonical review gates; this file only defines the end-to-end EDA workflow.

## 1. Establish the design contract

Capture only the information that affects the design:

- target project or a new project name;
- functional blocks and sheet boundaries;
- supply rails, input range, peak and continuous current, sequencing, and protection;
- external interfaces, connector pinout, signal levels, speed, and termination;
- exact ICs and preferred LCSC IDs, packages, substitutions, and assembly constraints;
- board outline, mounting holes, layer count, controlled impedance, creepage/clearance, and keep-outs;
- required outputs such as schematic, PCB, BOM, pick-and-place, Gerbers, or review screenshots.

If changing an existing project versus creating a new one would materially change the result, pause and ask. Do not invent electrical requirements.

## 2. Read the current state

Before writes:

1. Verify the bridge and connected EDA window.
2. Read current project and active document info.
3. Record a target lock containing `windowId`, `projectUuid`, `documentUuid`, and `documentType`; recheck it before each write batch.
4. Inventory relevant sheets, components, nets, footprints, board outline, layers, rules, and existing ERC/DRC findings.
5. Confirm the intended target and that unsaved work is not at risk.

If any target-lock field changes, stop before writing. On a partial batch failure, use recorded primitive IDs and readback to add only missing items.

## 3. Build the schematic in reviewable blocks

- Choose exact device records and build the compact device-evidence cards required by the schematic engineering standard before committing critical circuitry.
- Place by functional block with readable left-to-right signal flow and clear power domains.
- Give each functional block a short heading and enough whitespace to be recognized at full-sheet view. Use subtle block outlines only when they improve scanning and never let an outline cross wires, symbols, or text.
- Add decoupling, pull-ups or pull-downs, boot straps, programming and test points, protection, and no-connect markers only when electrically justified.
- Use consistent net names and explicit power/ground symbols. Keep short local connections visible; use ordinary net labels for same-sheet cross-block signals. Reserve input/output/bidirectional ports for actual sheet or hierarchy boundaries and give them the true direction; never use bidirectional ports as a visual substitute for net labels.
- After placement and again after wiring, inspect the rendered sheet at normal review zoom. Move or rotate attributes so no reference, value, net name, pin number, block title, wire, or symbol overlaps.
- Create and verify one functional block at a time. Read back component IDs, references, values, pins, wires, and nets after every batch.
- Apply the appropriate Draft, Review-ready, or Schematic-release gate. Run ERC and inspect the rendered sheet. Fix real connectivity errors; document intentional exceptions instead of hiding them.

## 4. Build the PCB from constraints

- Verify every schematic component has the intended footprint and that the netlist matches before placement.
- Establish outline, mounting holes, connector locations, layer stack, design rules, keep-outs, high-current paths, and sensitive zones before routing.
- Place mechanical and connector constraints first, then power, clocks, high-speed or analog-sensitive blocks, then remaining logic.
- Keep decouplers at the relevant power pins, minimize high-di/dt loops, respect return paths, and separate incompatible noise domains where justified.
- Complete a placement-only gate before the first trace: no footprint-body, pad, courtyard, keep-out, connector-access, or silkscreen overlaps; references are readable; functional grouping and routing channels are visually credible. If this gate fails, move components instead of routing around a bad floorplan.
- Route critical nets first. Use calculated width, clearance, via, differential-pair, and impedance rules; do not guess manufacturing constraints.
- Add planes, pours, stitching, test access, readable silkscreen, polarity and pin-1 markings, then rerun DRC.

## 5. Validate in layers

Keep these claims separate:

| Gate | Evidence |
| --- | --- |
| API execution | Bridge returned success and non-null IDs/results |
| Structural readback | Expected component, primitive, pin, net, and rule data was read back |
| Electrical checks | ERC/DRC completed and findings were resolved or explicitly accepted |
| Visual quality | Screenshots show readable labels, no overlaps, sane grouping and placement |
| Deliverables | Saved project and requested exports exist and open correctly |
| Hardware proof | Only measurements or board bring-up can prove real hardware behavior |

Stop once the requested scope passes its relevant gates. Do not expand a narrow schematic edit into a board redesign.
