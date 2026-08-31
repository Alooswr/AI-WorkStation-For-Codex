# Protocol Checklist (Minimal)

- Capture TX/RX with timestamps.
- Mark frame boundary, accepted/dropped, CRC fail.
- Include startup window (catch pre-init behavior).
- Verify frame wrapper mode and CRC mode are consistent on both sides.
- Verify notify dispatch uses correct field decode.
