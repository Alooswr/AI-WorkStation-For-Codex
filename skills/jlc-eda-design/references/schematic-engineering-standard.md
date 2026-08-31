# 原理图工程规范与放行清单

Read this reference before creating, materially reviewing, or releasing a schematic. Its purpose is to make the design electrically traceable, easy to review, and honest about what remains unverified. It is not a substitute for a product-specific safety, EMC, regulatory, or customer standard.

## 1. Use evidence, not visual imitation

Resolve a design decision in this order:

1. Applicable safety, regulatory, customer, and interface requirements.
2. Exact orderable-part datasheet, package drawing, and silicon errata.
3. Official device-family hardware design guide, reference design, and evaluation-board design files.
4. Official regulator, interface, RF, memory, sensor, or analog application notes and design tools.
5. Board-fabrication and assembly capabilities for the intended supplier.
6. Project conventions and general diagramming practice.

Do not copy a reference schematic merely because it looks authoritative. Record the source, exact device or board revision, operating assumptions, and every intentional deviation. If sources conflict, follow mandatory requirements and the publisher's explicit errata or supersession relationship; never choose by date alone. If equally applicable primary sources still conflict, keep the affected decision `TBD` and ask only when it changes safety, damage risk, bootability, or required behavior.

Public standards provide a common documentation language; they do not determine the correct capacitor, pull resistor, protection device, regulator loop, or boot state for an arbitrary chip. IEC 61082-1 covers general presentation of electrotechnical documents, IEC 60617 covers graphical-symbol semantics, and IEC 81346-1 covers unambiguous object structuring and reference designations. IPC-2612 is useful historical guidance on schematic-document completeness, but IPC currently lists the published edition as no longer maintained. Unless the user names an exact standard and edition and the applicable text is available, describe the result as passing this standard-informed quality gate, not as IPC/IEC/IEEE compliance or certification.

## 2. Set the maturity level

Label the result with one of these levels:

| Level | Allowed state | Forbidden claim |
| --- | --- | --- |
| Draft | Reversible assumptions and clearly marked `TBD` items may remain | Do not call it review-ready or electrically complete |
| Review-ready | Critical requirements, exact parts, pin mapping, and power/interface decisions are resolved | Do not call it released while findings remain unexplained |
| Schematic-release | All release gates below pass and the source/PDF revision is fixed | Do not call it PCB-, EMC-, safety-, manufacturing-, or hardware-validated |

If the user does not name a maturity level, default to `Draft`, state that assumption once, and continue; do not ask solely about maturity. Upgrade to `Review-ready` or `Schematic-release` only when the user requests it or the requested handoff clearly requires it.

Stop and ask for information only when an unknown can change safety, damage risk, connector pinout, power architecture, isolation, bootability, or a required interface. Consolidate discoverable blocking questions into one pass. For presentation-only choices, use a reversible project convention and continue.

## 3. Capture a design contract before drawing

Record the values that control the circuit:

- supply sources, nominal and min/max voltage, continuous and peak current, transients, sequencing, shutdown, and reverse-feed conditions;
- external connectors, mating orientation, pinout, signal direction, voltage domain, speed, cable environment, and hot-plug exposure;
- operating modes, reset and boot behavior, programming/debug path, clocks, wake sources, and low-power states;
- analog range, accuracy, bandwidth, source impedance, reference, filtering, and error budget where applicable;
- environmental, ESD/surge, isolation, creepage/clearance, thermal, and regulatory requirements;
- exact orderable parts, allowed substitutes, packages, DNP options, assembly side, and availability constraints;
- expected schematic outputs and the maturity level being requested.

Write unknown material requirements as explicit `TBD` items. Never hide them in a guessed component value or net connection.

## 4. Keep a device-evidence card for every critical part

For each MCU, processor, FPGA, regulator, charger, transceiver, isolation device, precision analog part, RF part, memory, and safety-critical protection device, keep a compact working record containing:

- manufacturer, exact MPN, chip-versus-module choice, package, silicon revision when relevant, LCSC ID when used, symbol source, footprint source, and pin-count cross-check;
- datasheet, hardware guide, and errata links or document identifiers, plus the applicable revision and section or page used for each critical decision;
- recommended operating limits separated from absolute maximum ratings;
- every power, ground, reference, exposed-pad, reset, enable, boot/strap, clock, debug, and programming pin;
- required external components and the source section that justifies each value or range;
- unused-pin disposition and power-off behavior;
- reference-design differences and their engineering reason.

Reflect layout-dependent requirements such as decoupler-to-pin association, crystal loop, switching-current loop, Kelvin sense, impedance, guard, thermal pad, antenna keep-out, and connector-side protection in schematic notes or constraints. A component shown near an IC on the schematic is not evidence that PCB placement will be correct.

## 5. Make the document easy to audit

- Organize multi-sheet designs by function. Use a cover/notes sheet when the design needs revision history, variants, or system constraints; give the power tree and each major function a clear home.
- Prefer one dominant signal flow, normally inputs on the left and outputs on the right. Put supplies above and returns below where practical, without distorting the true circuit.
- Put connectors and off-board interfaces at block or sheet boundaries. Show connector pin numbers and mating orientation unambiguously.
- Divide the sheet into recognizable functional regions and add concise region titles such as `POWER`, `MCU CORE`, `RESET / BOOT`, and `DEBUG / UART`. Keep enough whitespace between regions that their boundaries remain obvious at full-sheet view; decorative boxes must not cross electrical graphics.
- Keep short local connectivity visible. For long same-sheet connections, prefer ordinary net labels. Use off-sheet or hierarchical ports only at real sheet/hierarchy boundaries, and use input/output/bidirectional graphics only when the electrical direction is true. Never use a bidirectional arrow merely as a convenient named-net marker.
- If the active EDA/API version cannot create an ordinary net label, place it through the EDA UI or retain a clean explicit wire. Do not silently degrade the notation to a directional port.
- Use junction dots for connected crossings, avoid ambiguous four-way junctions, and keep unconnected crossings visually distinct.
- Do not route wires through symbols, values, notes, or other nets. Keep reference designators, values, MPNs where needed, and polarity markings readable at the normal review zoom.
- Keep ordinary labels and attributes horizontal where practical. Place each reference, value, rail name, and net label in reserved whitespace; do not stack text on a power symbol, component body, pin number, wire, or another attribute. Rotated text is acceptable only when the block layout still reads unambiguously at normal zoom.
- Use one naming convention for rails, active-low signals, differential pairs, buses, and directions. Never create aliases for the same electrical net merely to improve appearance.
- Keep reference designators unique and stable after review begins. Mark DNP/DNI and mutually exclusive build variants explicitly.
- Preserve the project's established reference-designator system. Common `R/C/U/J` prefixes are useful conventions but are not, by themselves, proof of IEC 81346 compliance; never hard-code unfamiliar IEC class letters from memory.
- Prefer a standard library symbol whose meaning matches the device. If formal IEC 60617 verification is requested, check the exact database symbol identity, status, application class, and restrictions; do not infer compliance from visual resemblance. Never rotate, mirror, simplify, or combine a symbol in a way that changes its meaning, terminal identity, or label readability.
- Account for every visible and hidden power pin. Mark every intentionally unconnected pin with an explicit no-connect marker or documented disposition.
- On every cross-sheet signal, make the source, destination, direction, and voltage domain discoverable without searching by coordinates.

## 6. Electrical review gates

### Power and grounding

- The power tree names every rail source, consumer, voltage tolerance, load budget, enable, power-good, sequence, and discharge or backfeed path.
- Every supply and reference pin is connected to the intended domain. Analog, digital, RF, PLL, memory, backup, and I/O domains are not collapsed by name without evidence.
- Regulator topology, input/output capacitor value and bias derating, ESR/stability limits, inductor, compensation, current limit, thermal loss, and startup behavior come from the exact controller documentation or an official design tool.
- Decoupling is traced per supply pin or pin group from the exact device guidance. Separate local high-frequency bypassing from bulk energy storage; do not apply a blanket `100 nF everywhere` rule.
- High-frequency bypass parts have an explicit short-loop placement intent. Ferrite beads and LC filters require impedance/current and resonance reasoning; they are not decorative noise cures.
- Connector power includes the required reverse-polarity, overvoltage, inrush, fuse/current limit, surge, ESD, and hot-plug analysis for its real environment.
- Powering and unpowering any attached device does not unintentionally back-power another domain through I/O or protection diodes.

### Reset, boot, clocks, and debug

- Reset and enable pins have deterministic states throughout ramp, reset, programming, sleep, and power-down. External pulls are checked against internal pulls, leakage, supervisors, slow ramps, and connected peripherals; open-drain and push-pull reset sources cannot contend.
- Boot and strap pins are checked at the actual sampling time and against every attached load. Keep a table of pin, sample event, internal pull, normal level, recovery/programming level, and attached loads; document assembly options.
- The programming/debug connector exposes the required signals, ground, target-voltage reference, reset, and any boot control; shared functional pins are reviewed for contention.
- Crystal or resonator part, frequency, tolerance, ESR, drive level, load capacitance, and capacitor calculation follow the exact device and crystal data. External clocks meet amplitude, bias, duty-cycle, and startup requirements.
- Reserved series/termination footprints are added only when an interface guide, simulation, or credible tuning need justifies them; their default population state is explicit.

### Digital interfaces

- Each signal has compatible source/output and receiver/input voltage thresholds across min/max supply and temperature. `3.3 V`, `5 V tolerant`, and `open drain` are never inferred from a signal name.
- Direction, bus ownership, tri-state behavior, pull resistors, level-shifter direction/enable, power-off isolation, and default states are explicit.
- Classify every unused pin from the exact datasheet. `NC`, `DNC`, `reserved`, internal-regulator capacitor, RF/crystal, strap, debug, and package-specific memory pins are not ordinary unused GPIO and must not receive a generic treatment.
- Differential pair polarity, reference voltage, common-mode range, termination, AC coupling, lane mapping, and swap permissions follow the exact interface and device documentation.
- External-facing lines have protection selected for the interface bandwidth, working voltage, capacitance, surge level, and grounding scheme. The schematic states that protection is placed at the connector boundary. Chip-level HBM/CDM qualification is not evidence that the finished product passes system-level ESD or surge requirements.

### Analog, sensing, and RF

- Inputs and outputs stay within common-mode, absolute, and linear operating ranges. Bias-current paths, source impedance, acquisition time, output drive, stability, gain, tolerance, noise, and filter corner are checked where relevant.
- ADC/DAC reference and analog supplies follow the converter's grounding and decoupling guidance. Do not split AGND and DGND by slogan; follow the device architecture and intended return-current path.
- RF matching, antenna, controlled-impedance, crystal, and keep-out networks are copied only from the exact approved variant or calculated and marked for tuning. Include measurement or tuning access when the vendor guide requires it.

### Test, variants, and service

- Provide accessible intent for key rails, reset, boot, clocks, programming/debug, and critical buses where bring-up or production test needs them.
- DNP parts, alternate supplies, bypass links, configuration resistors, and mutually exclusive population options cannot create an undocumented or unsafe combination.
- User-replaceable connectors, polarity-sensitive parts, pin 1, fuse rating, and service boundaries are obvious in both schematic and BOM data.

## 7. ERC is a detector, not proof

- Configure symbol pin electrical types and power-source behavior so ERC can find real errors. Do not silence an error by changing a pin to passive unless the device semantics justify it.
- Resolve every ERC finding or record a narrow waiver containing the affected net/pin, reason, and supporting source. Never blanket-disable a rule to obtain a clean report.
- Independently audit critical pin-to-net mappings, power pins, ground pins, NC/reserved pins, multi-unit symbols, hidden pins, connector numbering, and symbol-to-footprint pad mapping. ERC cannot prove these library facts.
- After any symbol replacement, package change, annotation, or major net-label edit, rerun the affected audits and ERC.

## 8. Visual review

Inspect the rendered schematic, not only API objects:

1. Full-sheet view: sheet hierarchy, signal flow, power domains, off-sheet destinations, and block spacing are understandable.
2. Normal review zoom: references, values, MPNs or notes, pin names/numbers, junctions, NC marks, and polarity are legible and do not overlap.
   Check every functional region separately; zero text-on-text, text-on-symbol, text-on-wire, and symbol-on-symbol overlap is the acceptance criterion, not merely an overall tidy impression.
3. Critical close-ups: power, reset/boot, clock, programming, connectors/protection, analog/RF, and dense buses match the evidence cards.
4. Exported PDF or image: page titles, revision, sheet numbering, fonts, line weights, and cross-references survive export and remain readable in grayscale.

An aesthetically tidy schematic with ambiguous pins is a failure. An electrically plausible netlist that reviewers cannot follow is also a failure.

## 9. Release gates

Before claiming `Schematic-release`, require all of the following:

- no unresolved material `TBD` items;
- exact MPN/package and verified symbol-to-footprint mapping for every populated part;
- device-evidence cards complete for critical parts and deviations from reference circuits recorded;
- power tree and load/sequence/backfeed review complete;
- reset, boot/strap, clock, programming/debug, protection, unused-pin, exposed-pad, and test-access review complete;
- critical pin-to-net and connector pin-number audits pass;
- ERC has no unexplained violations and every waiver is narrow and sourced;
- BOM variants and DNP states are unambiguous;
- rendered full-sheet and critical-area visual review passes;
- a fresh second-pass review compares the schematic directly against the source documents; for high-risk designs, obtain a genuinely independent reviewer;
- saved source and versioned PDF/export reopen correctly.

Report the gate evidence separately. A schematic release still does not prove PCB layout, signal/power integrity, thermal performance, EMC, safety certification, manufacturability, assembly correctness, firmware compatibility, or real hardware behavior.

## 10. Reject these shortcuts

- Choosing a symbol because its name matches without checking every symbol pin against the exact package.
- Copying an evaluation-board circuit without checking its device variant, power source, assembly options, test-only circuitry, and errata.
- Treating absolute maximum ratings as normal design targets.
- Adding generic decouplers, ferrites, TVS parts, pull resistors, or series resistors without a source or calculation.
- Grounding every exposed pad by convention; the exact package documentation may require ground, another net, or no connection.
- Hiding local wiring behind global labels, using net aliases, or relying on invisible power pins.
- Leaving unused, reserved, exposed-pad, or no-connect pins implicit.
- Calling an ERC-clean schematic electrically correct or production-ready.
- Assuming proximity on a schematic guarantees placement, return paths, impedance, creepage, thermal, or EMC behavior on the PCB.

## 11. Authoritative anchors

Use these as method anchors, then open the exact current device documents for the design at hand:

- IEC 60617 graphical symbols database: <https://webstore.iec.ch/en/publication/2723>
- IEC 61082-1 electrotechnical-document preparation rules: <https://webstore.iec.ch/en/publication/4469>
- IEC 81346-1 structuring and reference-designation principles: <https://webstore.iec.ch/en/publication/64021>
- IPC-2612 scope preview and official revision-status table: <https://www.ipc.org/TOC/IPC-2612.pdf> and <https://www.electronics.org/ipc-document-revision-table>
- Espressif hardware-design guidelines and schematic checklist: <https://docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32/index.html>
- ST AN4488 hardware-development guide: <https://www.st.com/resource/en/application_note/dm00115714.pdf>
- TI processor-family schematic design and review-checklist example: <https://www.ti.com/lit/pdf/sprado8>
- NXP MCX A hardware-design guide: <https://www.nxp.com/docs/en/application-note/AN14778.pdf>
- Analog Devices MT-101 decoupling tutorial: <https://www.analog.com/media/en/training-seminars/tutorials/MT-101.pdf>

Do not freeze these examples as universal component values. Use them to enforce the workflow: identify the exact part, read the applicable current source, design by evidence, and review with an explicit checklist.
