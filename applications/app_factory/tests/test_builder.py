import asyncio

import pytest

from applications.app_factory import builder
from applications.app_factory.bedrock_runtime import BuildError, ResultMessage


def test_options_route_coding_and_fast_agents_to_glm(monkeypatch):
    monkeypatch.setenv("APP_FACTORY_MODEL_ID", "zai.glm-4.7")
    monkeypatch.setenv("APP_FACTORY_FAST_MODEL_ID", "zai.glm-4.7-flash")
    opts = builder.build_agent_options("example")
    assert opts.model == "zai.glm-4.7"
    assert opts.agents["agent-builder"].model == opts.model
    assert opts.agents["validator"].model == opts.model
    assert opts.agents["docs-builder"].model == "zai.glm-4.7-flash"
    assert "validator" in opts.required_agents


def test_generation_error_blocks_final_validation(monkeypatch):
    async def failed_query(**kwargs):
        yield ResultMessage(is_error=True, errors=["budget exhausted"])
    monkeypatch.setattr(builder, "query", failed_query)
    monkeypatch.setattr(builder, "scaffold_ui", lambda _: [])
    def unexpected_validation(_):
        pytest.fail("Final validation must not run after generation failure")
    monkeypatch.setattr(builder, "validate_generated_files", unexpected_validation)
    with pytest.raises(BuildError, match="budget exhausted"):
        asyncio.run(builder.run_builder(builder.SAMPLE_ANSWERS))


def test_invalid_use_case_name_never_scaffolds(monkeypatch):
    monkeypatch.setattr(builder, "scaffold_ui", lambda _: pytest.fail("Unsafe path"))
    with pytest.raises(ValueError, match="identifier"):
        asyncio.run(builder.run_builder({**builder.SAMPLE_ANSWERS, "use_case_name": "../../existing"}))


def test_missing_artifacts_fail_even_if_import_could_pass(tmp_path, monkeypatch):
    monkeypatch.setattr(builder, "FSI_FOUNDRY", tmp_path)
    with pytest.raises(BuildError, match="Required generated files missing"):
        builder.validate_generated_files("example")
