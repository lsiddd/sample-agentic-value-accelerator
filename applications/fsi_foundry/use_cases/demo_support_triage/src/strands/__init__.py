"""
Demo Support Triage Use Case - Strands Implementation.

AI-powered support ticket triage for customer service demos
using the Strands agent framework.

The use case is automatically registered with the AVA registry on import.
"""

from .orchestrator import DemoSupportTriageOrchestrator, run_demo_support_triage
from .models import TriageRequest, TriageResponse

# Register this use case with the platform registry
from base.registry import register_agent, RegisteredAgent

# Register the demo support triage use case as an agent using the async entry point
register_agent(
    name="demo_support_triage",
    config=RegisteredAgent(
        entry_point=run_demo_support_triage,
        request_model=TriageRequest,
        response_model=TriageResponse,
    )
)

__all__ = [
    "DemoSupportTriageOrchestrator",
    "run_demo_support_triage",
    "TriageRequest",
    "TriageResponse",
]
