"""Custom domain tools for the demo_support_triage use case.

This use case does not require deterministic computation tools.
Classification and response drafting are LLM tasks handled by the agent.

If future requirements add formulas, thresholds, or fixed-category
classifications, add @tool-decorated functions here following the
canonical pattern from customer_service/src/strands/tools.py.
"""
