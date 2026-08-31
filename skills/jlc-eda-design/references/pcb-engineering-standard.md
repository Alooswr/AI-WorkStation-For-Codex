# PCB 工程布局、布线与放行清单

Read this reference before placing, routing, materially reviewing, or releasing a PCB. It defines the physical-layout and visual-quality gates that complement the schematic standard. It does not replace product-specific SI/PI, EMC, thermal, safety, RF, isolation, or manufacturing requirements.

## 1. Establish constraints before placement

- Resolve board outline, mounting holes, connector access, enclosure limits, assembly side, layer stack, copper weight, fabrication/assembly limits, keep-outs, and test access from the current project requirements and intended manufacturer's current capabilities.
- Carry schematic evidence into PCB constraints: power-pin-to-decoupler association, reset/boot requirements, crystal or switching loops, analog/reference returns, protection-at-connector intent, impedance, differential pairs, antenna or isolation keep-outs, and thermal paths.
- Do not invent a clearance, width, via, annular ring, impedance, creepage, or thermal rule. Use the actual design rule, a calculation, or a current manufacturer requirement; mark unresolved material constraints `TBD`.

## 2. Floorplan before detail placement

Place in this order unless a real mechanical constraint requires another sequence:

1. Board outline, mounting features, fixed connectors, controls, indicators, and keep-outs.
2. Power entry/protection and major power-conversion loops.
3. MCU/processor and clock, reset, boot, debug, and programming access.
4. Interface transceivers and connector-side protection.
5. Decouplers, references, filters, terminations, and remaining support parts.

Keep functional blocks recognizable. Align related parts consistently, keep connector pin order useful for routing, leave deliberate routing channels, and preserve physical access for cables, buttons, probes, and assembly tools. A compact board is not successful if its floorplan is visually tangled or forces avoidable crossovers.

## 3. Pre-route placement gate

Do not create the first trace until all of these pass:

- Every footprint body, pad, courtyard, component-height keep-out, board edge, mounting feature, and connector-access area is non-overlapping under the applicable rules.
- Decouplers are adjacent to their assigned supply/return pins with an obvious short-loop orientation; several capacitors are not piled into one unreadable cluster.
- Boot, reset, clock, analog, power, debug, and interface parts are placed by function rather than merely near the central IC.
- There is credible space for critical traces, return paths, fanout vias, copper pours, and test access.
- Reference designators, values that are intentionally shown, polarity marks, pin-1 marks, connector labels, and board identifiers are readable at normal review zoom. Silkscreen does not overlap pads, exposed copper, another component, or another text item.
- A rendered full-board screenshot and dense-area close-ups show no component-on-component, text-on-text, or text-on-pad overlap. API coordinates alone do not pass this gate.

When the gate fails, move or rotate components and their attributes. Do not route around a bad placement and do not hide all references merely to make the screenshot look clean.

## 4. Route by electrical priority

- Route power-entry, switching-current, crystal/clock, high-speed, differential, analog/reference, reset/boot, and other evidence-identified critical nets before ordinary GPIO.
- Fan out fine-pitch pins with widths and vias that meet the verified rules. Widen only after escaping the pin field; do not force a wide trace through adjacent pads.
- Keep return-current continuity under each signal. Avoid unnecessary layer changes and do not cut a reference plane with unrelated traces, slots, or fragmented pours.
- Minimize high-di/dt loop area and keep protection at the physical connector boundary. Keep noisy and sensitive regions apart only when justified by their real current and field paths.
- Use 45-degree or smooth routing where practical, remove needless jogs and stubs, and leave enough spacing that later copper and silkscreen remain manufacturable and readable.

## 5. Copper, vias, testability, and markings

- Rebuild every pour after routing and after any placement change. Verify its assigned net, island policy, clearance, thermal relief, neck-downs, and continuity; the visible presence of copper is not proof of connection.
- Add stitching vias only where they improve a documented return, shielding, thermal, or EMC path. Do not distribute decorative vias without purpose.
- Keep debug/programming, reset, boot, key rails, and critical buses accessible for bring-up when the product requires them.
- Move silkscreen attributes deliberately after placement and routing. Keep a stable orientation, readable size, visible pin-1/polarity information, connector signal labels where useful, and a board name/revision when requested.

## 6. PCB validation gates

Validate and report these separately:

1. **Structural readback:** correct board/document lock, component and footprint count, nets, pad mapping, layers, outline, rules, and generated primitives.
2. **Placement:** the pre-route gate passed before routing; no physical or silkscreen overlap remains in rendered views.
3. **Connectivity:** expected nets are routed or intentionally left open; pours were rebuilt; no unintended island or unconnected critical pad remains.
4. **DRC:** every finding is fixed or has a narrow, sourced waiver. A boolean API success without inspected settings is insufficient for release.
5. **Visual review:** full board plus dense, connector, power, clock, and fine-pitch close-ups are legible and plausibly manufacturable.
6. **Manufacturing outputs:** requested Gerber, drill, BOM, pick-and-place, drawings, and previews exist and reopen correctly.
7. **Hardware proof:** assembly, power-up, programming, measurements, SI/PI/EMC/thermal tests, and functional bring-up are separate gates.

## 7. Reject these shortcuts

- Starting routing while footprints, courtyards, silkscreen, or attributes overlap.
- Treating a visually small coordinate distance as adequate without checking actual footprint geometry and design rules.
- Placing all decouplers in a dense cluster with ambiguous pin association.
- Solving a crossover created by poor connector/component orientation with excessive vias or long perimeter traces before reconsidering placement.
- Calling a ratsnest reduction, copper pour, DRC pass, or attractive screenshot proof of electrical, mechanical, manufacturing, or hardware correctness.
