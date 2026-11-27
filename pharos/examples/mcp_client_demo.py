"""Call the Pharos MCP server the way an agent would: list tools, then run all three on a sample package.

    python examples/mcp_client_demo.py [package_dir] [recovery_target_weeks]
"""
import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent.parent


async def main(package: str, target: float | None) -> None:
    params = StdioServerParameters(command=sys.executable, args=["-m", "pharos.server"], cwd=str(ROOT), env={**os.environ, "PHAROS_DB": ":memory:"})
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
            print("tools:", [t.name for t in tools])
            args: dict = {"package_dir": package, "case_id": "mcp-demo"}
            if target is not None:
                args["recovery_target_weeks"] = target
            decision = json.loads((await session.call_tool("recovery_brief", args)).content[0].text)
            print("\nanswer  :", decision["answer"])
            print("headline:", decision["headline"])
            compare = json.loads((await session.call_tool("compare_substitution", {"case_id": "mcp-demo"})).content[0].text)
            screen = json.loads((await session.call_tool("screen_consequences", {"case_id": "mcp-demo"})).content[0].text)
            print("\ncompare :", compare["summary"])
            for f in screen["findings"]:
                print(f"finding : [{f['label']:14}] {f['title']}")
            print("\nengineer questions:", *decision["engineer_questions"], sep="\n  - ")
            print("vendor questions  :", *decision["vendor_questions"], sep="\n  - ")


if __name__ == "__main__":
    pkg = sys.argv[1] if len(sys.argv) > 1 else "samples/dev/dev-01-oakridge"
    tgt = float(sys.argv[2]) if len(sys.argv) > 2 else None
    asyncio.run(main(pkg, tgt))
