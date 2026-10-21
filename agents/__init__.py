"""Echo Pitch multi-agent layer (Microsoft Agent Framework + Azure AI Foundry, with an offline fallback)."""
from .config import Settings
from .orchestrator import MatchOrchestrator, Prefs

__all__ = ["Settings", "MatchOrchestrator", "Prefs"]
