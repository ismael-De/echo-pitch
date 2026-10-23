"""Runtime configuration from environment variables.

LLM_MODE                       offline | foundry  (default: foundry if an endpoint is set, else offline)
FOUNDRY_PROJECT_ENDPOINT       https://<account>.services.ai.azure.com/api/projects/<project>
  (alias AZURE_AI_PROJECT_ENDPOINT)
FOUNDRY_MODEL                  model deployment name, e.g. gpt-5-mini
  (alias AZURE_AI_MODEL_DEPLOYMENT_NAME)
LLM_TIMEOUT_S                  per-agent call timeout (default 20)
LLM_MAX_COMPLETION_TOKENS      output-token cap per call (default 400; recap 500)
LLM_REASONING_EFFORT           minimal | low | medium (gpt-5 family; default minimal). Unset or empty keeps minimal
LLM_PERSONA_REWRITE            1 = extra Persona LLM pass (default 0: persona context is folded into prompts)
FOUNDRY_CREDENTIAL             auto | cli | managed | default
LLM_RETRIES                    retries before the template fallback (default 1)
ECHO_FAULT_AGENTS              comma list of agents whose FIRST call fails (demo of retry/recovery),
                               e.g. "narrator,moments"; "narrator!" fails every call (forces fallback)
Auth uses DefaultAzureCredential (az login locally, managed identity on Azure Container Apps).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(*names: str, default: str | None = None) -> str | None:
    for n in names:
        v = os.environ.get(n)
        if v:
            return v
    return default


def load_dotenv(path: str | None = None) -> None:
    """Minimal .env loader (repo root); never overrides variables already set in the environment."""
    from pathlib import Path
    p = Path(path) if path else Path(__file__).resolve().parent.parent / ".env"
    if os.environ.get("ECHO_NO_DOTENV") or not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


@dataclass
class Settings:
    mode: str = "offline"
    project_endpoint: str | None = None
    model: str | None = None
    timeout_s: float = 8.0
    retries: int = 1
    max_completion_tokens: int = 400
    reasoning_effort: str | None = "minimal"
    persona_rewrite: bool = False   # extra LLM pass by the Persona agent (off by default to save cost)
    fault_once: set[str] = field(default_factory=set)
    fault_always: set[str] = field(default_factory=set)
    warning: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        ep = _env("FOUNDRY_PROJECT_ENDPOINT", "AZURE_AI_PROJECT_ENDPOINT")
        model = _env("FOUNDRY_MODEL", "AZURE_AI_MODEL_DEPLOYMENT_NAME", default="gpt-5-mini")
        mode = (_env("LLM_MODE", default="foundry" if ep else "offline") or "offline").lower()
        warning = None
        if mode == "foundry" and not ep:
            mode, warning = "offline", "LLM_MODE=foundry but no FOUNDRY_PROJECT_ENDPOINT; using offline templates"
        faults = [f.strip().lower() for f in (_env("ECHO_FAULT_AGENTS", default="") or "").split(",") if f.strip()]
        return cls(mode=mode, project_endpoint=ep, model=model,
                   timeout_s=float(_env("LLM_TIMEOUT_S", default="20")), retries=int(_env("LLM_RETRIES", default="1")),
                   max_completion_tokens=int(_env("LLM_MAX_COMPLETION_TOKENS", default="400")),
                   reasoning_effort=(_env("LLM_REASONING_EFFORT", default="minimal") or None),
                   persona_rewrite=_env("LLM_PERSONA_REWRITE", default="0") in ("1", "true", "yes"),
                   fault_once={f for f in faults if not f.endswith("!")},
                   fault_always={f[:-1] for f in faults if f.endswith("!")}, warning=warning)
