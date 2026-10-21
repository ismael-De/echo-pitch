import os

# Unit tests must not pick up a developer's .env (Foundry credentials) unless explicitly asked.
if not os.environ.get("ECHO_FOUNDRY_IT"):
    os.environ["ECHO_NO_DOTENV"] = "1"
    os.environ.setdefault("LLM_MODE", "offline")
