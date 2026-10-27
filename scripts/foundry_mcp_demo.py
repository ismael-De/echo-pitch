"""A Microsoft Agent Framework agent on Azure AI Foundry that uses the Echo Pitch MCP server as its tools.

python scripts/foundry_mcp_demo.py [--mcp https://<app>/mcp/] "Fact-check: Saltmarsh FC won 4-1"
Needs FOUNDRY_PROJECT_ENDPOINT (+ az login).
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_framework import Agent, MCPStreamableHTTPTool  # noqa: E402
from agent_framework.foundry import FoundryChatClient  # noqa: E402

from agents.config import Settings  # noqa: E402
from agents.foundry import _credential  # noqa: E402


async def main(url: str, question: str):
    s = Settings.from_env()
    client = FoundryChatClient(project_endpoint=s.project_endpoint, model=s.model, credential=_credential())
    async with MCPStreamableHTTPTool(name="echo-pitch", url=url) as mcp:
        agent = Agent(client=client, name="echo-mcp-demo", tools=[mcp],
                      instructions="You are a broadcast fact-checker. Use the echo-pitch tools; match EP-2026-002 "
                                   "unless told otherwise. Answer in at most two sentences.")
        resp = await agent.run(question)
        print(resp.text)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mcp", default="https://echo-pitch-web.blackriver-a826d80e.uaenorth.azurecontainerapps.io/mcp/")
    ap.add_argument("question", nargs="?", default="Fact-check this line: 'Saltmarsh FC beat Brackenridge Town 4-1.' "
                                                    "What was the real score and xG?")
    a = ap.parse_args()
    asyncio.run(main(a.mcp, a.question))
