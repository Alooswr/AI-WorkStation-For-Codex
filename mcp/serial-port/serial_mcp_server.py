"""Read-only serial-port discovery MCP server for local Codex clients."""

from __future__ import annotations

from serial.tools import list_ports
from mcp.server.fastmcp import FastMCP


mcp = FastMCP(
    "serial-port",
    instructions=(
        "Use serial_list_ports to enumerate local serial ports without opening "
        "or changing any device."
    ),
)


@mcp.tool()
def serial_list_ports() -> list[dict[str, str | int | None]]:
    """List local serial ports and USB metadata without opening a port."""

    ports: list[dict[str, str | int | None]] = []
    for port in sorted(list_ports.comports(), key=lambda item: item.device.lower()):
        ports.append(
            {
                "device": port.device,
                "name": port.name,
                "description": port.description,
                "hwid": port.hwid,
                "vid": port.vid,
                "pid": port.pid,
                "serial_number": port.serial_number,
                "location": port.location,
                "manufacturer": port.manufacturer,
                "product": port.product,
                "interface": port.interface,
            }
        )
    return ports


if __name__ == "__main__":
    mcp.run(transport="stdio")
