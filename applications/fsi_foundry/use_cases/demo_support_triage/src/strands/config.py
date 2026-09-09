"""
Demo Support Triage Use Case Configuration (Strands Implementation).

Support-triage-specific settings extending the base configuration.
Includes data paths, agent model settings, and triage thresholds.
"""

from config.settings import Settings, get_regional_model_id


class DemoSupportTriageSettings(Settings):
    """Demo support triage specific settings extending base configuration."""

    # Data configuration
    data_prefix: str = "samples/demo_support_triage"

    # Agent configuration - use regional model IDs
    # Note: These will be overridden by effective_bedrock_model_id in agents
    # that use the base class properly
    _base_model: str = "anthropic.claude-haiku-4-5-20251001-v1:0"

    @property
    def support_triage_agent_model(self) -> str:
        """Get regional model ID for support triage agent."""
        return get_regional_model_id(self.aws_region, self._base_model)

    # Use case specific thresholds
    max_response_time_seconds: int = 30
    confidence_threshold: float = 0.7
    escalation_urgency_threshold: str = "high"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


def get_demo_support_triage_settings() -> DemoSupportTriageSettings:
    """Get demo support triage specific settings instance."""
    return DemoSupportTriageSettings()
