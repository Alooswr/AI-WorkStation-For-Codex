---
name: mf-serial-hmi
description: Minimal workflow for M&F/DaCai serial HMI debugging. Use when tasks mention serial screen, 串口屏, 大彩, 美方, VisualTFT, `.tftprj`, UART frame parsing, `DeviceEnableCRC`, CRC, notify, `0xEE` frames, control notifications, or screen-vs-MCU protocol mismatch. Do not use for unrelated UART devices, generic serial logging, LVGL UI, or Keil compile-only work.
---

# M&F Serial HMI (Minimal)

Use this when debugging M&F/DaCai screen link issues.

## Use When

- The task mentions M&F/DaCai, 串口屏, 大彩, 美方, VisualTFT, `.tftprj`,
  `DeviceEnableCRC`, CRC, notify, or `0xEE` frames.
- The failure is a screen-to-MCU UART frame, CRC, notification parse, or
  configuration mismatch.

## Do Not Use When

- The UART task is not this serial HMI protocol.
- The UI stack is LVGL rather than M&F/DaCai serial HMI.
- The task is only Keil compile/link triage.

## Must-Check Order

1. `.tftprj`: `DeviceEnableCRC`, `DeviceBaudRate`, `DeviceControlNotify`, `DeviceScreenNotify`.
2. MCU parser framing: head/tail requirements and pre-parse drop rules.
3. CRC mode sync: screen `DeviceEnableCRC` == MCU `CRC16_ENABLE`.
4. Init phase behavior: queue/defer/ignore before link ready.
5. Notify decode path: `cmd_type`, `ctrl_msg`, `control_type`.

## Known Baseline

- Official demo frame: `0xEE ... 0xFF 0xFC 0xFF 0xFF`.
- Strict parser drops bytes that do not match frame entry conditions.
- CRC mismatch causes frame reject even if bytes look complete.

## Output Format

1. Screen vs MCU config diff.
2. Exact mismatch point.
3. Minimal patch plan.
4. UART capture checklist.
