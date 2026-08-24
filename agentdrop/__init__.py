"""AgentDrop — vision-first computer-use browser agents.

The core idea: agents do NOT parse the DOM. They screenshot the screen,
a vision model reasons about the pixels, and the agent acts with
mouse/keyboard at absolute pixel coordinates — exactly how a human
uses a browser. Every action is verified with a fresh screenshot.
"""

__version__ = "0.1.0"

from .loop.computer_use import ComputerUseLoop, LoopConfig, CampaignResult  # noqa: F401
from .loop.metrics import Metrics, TARGETS  # noqa: F401
from .registry.registry import ProfileRegistry, RegistryError  # noqa: F401
from .campaigns.base import Campaign, TaskSpec  # noqa: F401
