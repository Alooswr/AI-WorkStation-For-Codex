---
name: embedded-project-closeout
description: Close out an embedded firmware project by enumerating every required app, bootloader, and device-side target; reproducibly building .bin/.hex pairs; applying a parameterized organization release naming rule; and copying verified artifacts into the user-designated project archive. Use for explicit project completion, formal release, or archive requests, not ordinary development builds, debug images, or flashing.
---

# Embedded Project Closeout

Produce a complete, traceable firmware archive without disturbing any source checkout.

## Establish the Release Set

- Treat this as a final-release workflow only when the user explicitly says the project is complete, being released, or being archived.
- Discover every real firmware target across the project and linked repositories: application, bootloader, and each distinct endpoint or side. Do not invent targets, and do not silently omit one that fails.
- For every target, record the repository path, exact commit or requested working-tree state, build target, software role, exact MCU part number, software version, release type, and release date.
- Read chip and version fields from authoritative project or source definitions. If a component has no independent version, reuse a shared package version only when the repository already establishes that policy or the user confirms it; otherwise ask before naming.
- The configured archive root is `<ARCHIVE_ROOT>`. Resolve it from a local, untracked setting before use and honor an explicit task override.
- Preserve the existing project-oriented layout. The default is `<archive-root>\<ProductModel>\<ORG_PREFIX>-<ProductModel>-<YYYYMMDD>`. Do not reorganize an existing project folder without approval.

## Preserve Source State

- Capture Git status and provenance before building.
- Build from an isolated snapshot. For a remote ref, fetch and archive the exact commit. For a requested dirty working tree, copy that working state to an isolated directory.
- Never reset, clean, stash, switch, or build in the user's checkout merely to produce release artifacts.
- After packaging, verify the original repositories have the same status and commit as before.

## Build Every Target

- Use `embedded-skill-router` to select the appropriate build workflow for each target.
- Perform a clean or full rebuild in the isolated snapshot. For Keil, valid evidence requires the canonical `X Error(s), Y Warning(s)` summary; a process exit code alone is insufficient.
- Produce both `.bin` and Intel HEX for every target. If the project generates only one format, use the matching compiler toolchain converter, such as the same Arm Compiler `fromelf` used for the build.
- Check that BIN is non-empty and HEX has a valid Intel HEX start plus EOF record.
- Do not flash hardware unless the user separately requests it. Build success is not hardware-behavior proof.

## Apply the Organization Name

Use this exact field order:

```text
{OrgPrefix}{ProductModel}_{SoftwareRole}_{MainChip}_{Release|Demo}_{Version}_{YYYYMMDD}[_{SpecialApprovalId}].{bin|hex}
```

- Join the locally configured organization prefix directly to the normalized product model.
- Use a stable, unambiguous role such as `OnboardApp`, `OnboardBootloader`, `GroundApp`, or `ReceiverApp`.
- Use the exact MCU part number from the authoritative project definition.
- Include leading `V` exactly once in the version.
- Omit the special-approval field for a standard release.
- Use the software release date, not an arbitrary file timestamp.

For deterministic naming, copying, conflict refusal, and SHA-256 verification, run:

```powershell
powershell -NoProfile -File scripts/package_firmware_pair.ps1 `
  -BinPath <built.bin> -HexPath <built.hex> `
  -DestinationDirectory <project-release-folder> `
  -OrgPrefix ACME -ProductModel DEMO100 -Role OnboardApp -Chip MCU123 `
  -SoftwareType Release -Version V1.0.0 -ReleaseDate 20260101
```

The destination directory must already be resolved. The script copies rather than moves source artifacts, accepts an identical existing file as idempotent, and refuses a same-name file with different content.

## Completion Gate

- Expected firmware artifact count is two times the number of release targets.
- Verify each build result, final filename, byte size, and SHA-256 after copying.
- Keep all BIN/HEX pairs in the selected project release folder. Do not create or update a ZIP unless the user asks.
- Report exact source provenance, target names, compiler/toolchain, build summaries, archive path, hashes, unchanged source status, and any component that remains unbuilt.
- Do not call the project complete if any required target or either output format is missing.
