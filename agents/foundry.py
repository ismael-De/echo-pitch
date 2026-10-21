"""Microsoft Agent Framework agents backed by a Microsoft Foundry model deployment.

Only imported when LLM_MODE=foundry, so the offline path has no Azure dependency at runtime.
Cost controls: reasoning effort "minimal" (gpt-5 family), capped output tokens (LLM_MAX_COMPLETION_TOKENS,
sent as the Responses API max_output_tokens), no temperature (gpt-5-mini rejects non-default values),
and only key moments / insights / recap are ever sent to the model.
"""
from __future__ import annotations

import os
from typing import Any, Callable, Sequence

from .config import Settings

COMMON = ("Use ONLY the facts given; never invent players, numbers or events. Distances are metres. "
          "Language: 'en' = English; 'ar' = Modern Standard Arabic in a TV-commentary register, keep player and "
          "club names in Latin script, write numbers as digits. Audience: 'analyst' = precise and tactical, "
          "cite the key metric; 'fan' = warm, simple and emotional, no jargon. If a favourite club is given, "
          "speak from that supporter's perspective, but stay accurate about which team did what. Refer to teams by "
          "their names, never as 'home' or 'away'. Never quote internal field names or raw model values (momentum, "
          "importance, pressure levels); describe them in words. Return plain text only, no markdown, no quotes.")

INSTRUCTIONS = {
    "stats": ("You are the Stats agent for a live football broadcast. Call get_live_stats (and other tools if "
              "useful) and give ONE insight sentence (max 30 words) about the current balance of the match. " + COMMON),
    "moments": ("You are the Moments agent. Given a key-moment JSON and its match context, explain in at most two "
                "sentences (max 45 words) WHY the moment matters: game state, timing, run of play, chance quality "
                "(xG), control vs chaos or pressure. " + COMMON),
    "narrator": ("You are the Narrator agent, a live football commentator. Write exactly ONE vivid commentary "
                 "line (max 25 words) about the single event described. Never summarise the match. " + COMMON),
    "recap": ("You are the Narrator agent writing the full-time recap for a broadcast. Write 4-5 sentences (max "
              "110 words): result, whether it was deserved on xG, the decisive moments in order, and the player of "
              "the match given. " + COMMON),
    "persona": ("You are the Persona agent. Rewrite the given text for the target audience and favourite "
                "club/player, keeping the language and every fact. Max 45 words. " + COMMON),
}


def _credential():
    """Managed identity on Azure Container Apps; az CLI login locally; DefaultAzureCredential otherwise."""
    mode = os.environ.get("FOUNDRY_CREDENTIAL", "auto").lower()
    from azure.identity import aio as ident
    if mode == "cli" or (mode == "auto" and not os.environ.get("CONTAINER_APP_NAME") and _has_az()):
        return ident.AzureCliCredential()
    if mode == "managed" or (mode == "auto" and os.environ.get("CONTAINER_APP_NAME")):
        return ident.ManagedIdentityCredential(client_id=os.environ.get("AZURE_CLIENT_ID"))
    return ident.DefaultAzureCredential()


def _has_az() -> bool:
    import shutil
    return shutil.which("az") is not None


def build_agents(settings: Settings, stats_tools: Sequence[Callable[..., Any]]) -> dict[str, Any]:
    """Create one Agent Framework `Agent` per specialist, sharing one FoundryChatClient."""
    from agent_framework import Agent
    from agent_framework.foundry import FoundryChatClient

    client = FoundryChatClient(project_endpoint=settings.project_endpoint, model=settings.model,
                               credential=_credential())
    opts: dict[str, Any] = {"max_tokens": settings.max_completion_tokens}
    if settings.reasoning_effort:
        opts["reasoning"] = {"effort": settings.reasoning_effort}
    agents = {}
    for name, instr in INSTRUCTIONS.items():
        o = dict(opts)
        if name == "narrator":
            o["max_tokens"] = min(settings.max_completion_tokens, 200)  # one line
        if name == "recap":
            o["max_tokens"] = max(settings.max_completion_tokens, 500)
        a = Agent(client=client, name=f"echo-{name}", instructions=instr, default_options=o,
                  tools=list(stats_tools) if name == "stats" else None)
        a.echo_usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0}
        agents[name] = a
    return agents


async def run_text(agent: Any, prompt: str) -> str:
    resp = await agent.run(prompt)
    u = getattr(resp, "usage_details", None) or {}
    acc = getattr(agent, "echo_usage", None)
    if acc is not None:
        acc["calls"] += 1
        acc["input_tokens"] += int(u.get("input_token_count") or 0)
        acc["output_tokens"] += int(u.get("output_token_count") or 0)
        acc["reasoning_tokens"] += int(u.get("reasoning_output_token_count") or 0)
    text = (getattr(resp, "text", None) or "").strip()
    if not text:
        raise RuntimeError("empty LLM response")
    return text
