"""
Demo Support Triage Orchestrator (Strands Implementation).

Orchestrates the support triage workflow for classifying tickets
and drafting responses in a customer service demo.
"""
import json
import uuid
from datetime import datetime
from typing import Dict, Any
from base.strands import StrandsOrchestrator
from .agents import SupportTriageAgent
from .agents.support_triage_agent import triage_ticket
from utils.json_extract import extract_json
from .models import TriageRequest, TriageResponse, TriageMode, TicketCategory, UrgencyLevel

class DemoSupportTriageOrchestrator(StrandsOrchestrator):
    """
    Demo Support Triage Orchestrator using StrandsOrchestrator base class.

    Coordinates the Support Triage Agent for comprehensive ticket analysis
    and response drafting.
    """
    name = 'demo_support_triage_orchestrator'
    system_prompt = "You are a Senior Support Supervisor for a customer service demo.\n\nYour role is to:\n1. Coordinate the support triage workflow\n2. Ensure tickets are properly classified and prioritized\n3. Review drafted responses for quality and appropriateness\n4. Maintain high standards for customer service\n\nWhen creating the final summary, consider:\n- Accuracy of the ticket classification\n- Appropriateness of the urgency level\n- Quality and tone of the suggested response\n- Overall customer satisfaction potential\n\nBe concise but thorough. Your summary will be used by demo support operators.\n\n# BEGIN INPUT_CONSTRAINT (deterministic, do not edit by hand)\nINPUT CONSTRAINT (authoritative, overrides any earlier instruction):\nThe user request contains ONLY these fields:\n  - ticket_id: string (entity identifier)\n  - triage_mode: enum of ['full', 'classify_only', 'draft_only']\n  - additional_context\nNever ask for, infer, or fabricate any field outside this list.\nIf you need related data (e.g., profile, documents, history), fetch it\nvia the tools provided using the identifier above — do NOT request that\ndata from the user in your response.\n# END INPUT_CONSTRAINT"

    def __init__(self):
        super().__init__(agents={'support_triage_agent': SupportTriageAgent()})

    def _prefetch_data(self, ticket_id: str) -> dict:
        """
        Pre-fetch ticket data from S3.

        Args:
            ticket_id: Ticket identifier

        Returns:
            Dictionary with pre-fetched ticket data
        """
        from tools.s3_retriever_strands import s3_retriever_tool
        profile = json.loads(s3_retriever_tool(ticket_id, 'profile'))
        return {'profile': profile}

    def _build_input_text(self, ticket_id: str, data: dict, context: str | None=None) -> str:
        """
        Build input text for the triage agent.

        Args:
            ticket_id: Ticket identifier
            data: Pre-fetched ticket data
            context: Additional context

        Returns:
            Formatted input text
        """
        return f"Analyze support ticket: {ticket_id}\n\nPre-fetched ticket data (do NOT request more):\n```json\n{json.dumps(data, indent=2)}\n```\n\n{('Additional Context: ' + context if context else '')}\n\nClassify the ticket, determine urgency, and draft a professional response."

    def run_triage(self, ticket_id: str, triage_mode: str='full', context: str | None=None) -> Dict[str, Any]:
        """
        Run the support triage workflow.

        Args:
            ticket_id: Ticket identifier
            triage_mode: Type of triage (full, classify_only, draft_only)
            context: Additional context for the triage

        Returns:
            Dictionary with triage results
        """
        data = self._prefetch_data(ticket_id)
        input_text = self._build_input_text(ticket_id, data, context)
        result = self.run_agent('support_triage_agent', input_text)
        return {'ticket_id': ticket_id, 'triage_mode': triage_mode, 'agent_result': result.output}

    async def arun_triage(self, ticket_id: str, triage_mode: str='full', context: str | None=None) -> Dict[str, Any]:
        """
        Async version of run_triage.

        Args:
            ticket_id: Ticket identifier
            triage_mode: Type of triage (full, classify_only, draft_only)
            context: Additional context for the triage

        Returns:
            Dictionary with triage results
        """
        data = self._prefetch_data(ticket_id)
        ticket_data_json = json.dumps(data, indent=2)
        triage_result = await triage_ticket(ticket_id, ticket_data_json, context)
        return {'ticket_id': ticket_id, 'triage_mode': triage_mode, 'agent_result': triage_result['analysis']}

async def run_demo_support_triage(request):
    """Run the triage workflow."""
    orchestrator = DemoSupportTriageOrchestrator()
    final_state = await orchestrator.arun_triage(ticket_id=request.ticket_id, triage_mode=request.triage_mode.value if hasattr(request.triage_mode, 'value') else str(request.triage_mode), context=getattr(request, 'additional_context', None))
    category = TicketCategory.OTHER
    urgency = UrgencyLevel.LOW
    suggested_response = ''
    reasoning = ''
    confidence = 0.5
    try:
        structured = extract_json(final_state.get('agent_result', '{}'))
        category_str = structured.get('category', 'other')
        try:
            category = TicketCategory(category_str)
        except ValueError:
            category = TicketCategory.OTHER
        urgency_str = structured.get('urgency', 'low')
        try:
            urgency = UrgencyLevel(urgency_str)
        except ValueError:
            urgency = UrgencyLevel.LOW
        suggested_response = structured.get('suggested_response', '')
        reasoning = structured.get('reasoning', '')
        confidence = float(structured.get('confidence', 0.5))
    except Exception:
        reasoning = str(final_state.get('agent_result', ''))[:500]
    return TriageResponse(ticket_id=request.ticket_id, category=category, urgency=urgency, suggested_response=suggested_response, reasoning=reasoning, confidence=confidence, timestamp=datetime.utcnow(), raw_analysis={'agent_result': final_state.get('agent_result')})
