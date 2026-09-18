"""Tests for :class:`backend.service.config.ConfigManager` options metadata."""

from __future__ import annotations

from backend.service.config import (
    HARBOR_PERSONA_MODEL_ENV,
    PERSONA_MODEL_ENV,
    PERSONA_MODEL_OPTIONS,
    PERSONA_MODEL_PROVIDER_KEYS,
    persona_model,
)


def _clear_provider_credentials(monkeypatch) -> None:
    """Drop every provider credential plus the explicit model pin.

    Keeps the catalog assertions independent of the machine running the tests:
    with nothing configured the picker falls back to the full catalog.
    """
    for env_names in PERSONA_MODEL_PROVIDER_KEYS.values():
        for name in env_names:
            monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv(PERSONA_MODEL_ENV, raising=False)
    monkeypatch.delenv(HARBOR_PERSONA_MODEL_ENV, raising=False)


def test_domain_allows_all_three(config_manager):
    # ALLOWED still carries every domain; validation accepts each.
    assert set(config_manager.ALLOWED["domain"]) == {"movie", "beauty_product", "game"}
    for d in ("movie", "beauty_product", "game"):
        config_manager.validate({"domain": d})  # must not raise


def test_application_id_allows_generic_chatbot_applications(config_manager):
    assert config_manager.ALLOWED["applicationId"] == [
        "meal_planning_nutrition",
        "finance_openbb",
        "acme_support_api",
        "acme_support_mcp",
    ]
    for application_id in (
        "meal_planning_nutrition",
        "finance_openbb",
        "acme_support_api",
        "acme_support_mcp",
    ):
        config_manager.validate({"applicationId": application_id})


def test_options_returns_enriched_knobs(config_manager):
    opts = config_manager.options()
    assert set(opts.keys()) == {"knobs", "defaults", "environment"}

    knobs = {k["key"]: k for k in opts["knobs"]}
    # Editable knobs only — rankerMode / resourceMode are environment facts.
    assert set(knobs.keys()) == {
        "applicationId",
        "engine",
        "personaModel",
        "domain",
        "botType",
    }

    for knob in opts["knobs"]:
        assert set(knob.keys()) >= {
            "key",
            "label",
            "description",
            "options",
            "rebuildsAgent",
        }
        assert knob["label"]  # non-empty human label
        assert isinstance(knob["rebuildsAgent"], bool)
        for option in knob["options"]:
            assert set(option.keys()) >= {"value", "label", "description"}
            assert option["label"]


def test_options_knob_values_match_allowed(config_manager, monkeypatch):
    _clear_provider_credentials(monkeypatch)
    opts = config_manager.options()
    knobs = {k["key"]: k for k in opts["knobs"]}
    for key in ("applicationId", "engine", "domain", "botType"):
        values = [o["value"] for o in knobs[key]["options"]]
        assert values == config_manager.ALLOWED[key]
    assert [o["value"] for o in knobs["personaModel"]["options"]] == PERSONA_MODEL_OPTIONS
    assert "anthropic/claude-opus-4-8" in PERSONA_MODEL_OPTIONS
    assert "dashscope/qwen3.7-max" in PERSONA_MODEL_OPTIONS
    assert "dashscope/deepseek-v4-pro" in PERSONA_MODEL_OPTIONS
    assert "openrouter/z-ai/glm-4.7" in PERSONA_MODEL_OPTIONS
    assert "openrouter/anthropic/claude-haiku-4.5" in PERSONA_MODEL_OPTIONS
    assert "openai/gpt-5.4" in PERSONA_MODEL_OPTIONS
    assert "openai/gpt-5.5" in PERSONA_MODEL_OPTIONS
    assert "gemini/gemini-2.5-flash" in PERSONA_MODEL_OPTIONS
    assert "gemini/gemini-2.5-pro" in PERSONA_MODEL_OPTIONS
    assert "gemini/gemini-2.5-computer-use-preview-10-2025" in PERSONA_MODEL_OPTIONS
    assert "xai/grok-4.5" in PERSONA_MODEL_OPTIONS
    assert "xai/grok-3-mini" in PERSONA_MODEL_OPTIONS
    assert "deepseek/deepseek-v4-pro" in PERSONA_MODEL_OPTIONS
    assert "deepseek/deepseek-flash" in PERSONA_MODEL_OPTIONS
    assert "zai/glm-5" in PERSONA_MODEL_OPTIONS
    assert "zai/glm-4.7" in PERSONA_MODEL_OPTIONS


def test_persona_model_options_follow_configured_credentials(config_manager, monkeypatch):
    """只列出已配置凭据的 provider 的模型（本机只剩 DeepSeek 时不应再出现 Claude/GPT）。

    发现请求由 conftest 的 autouse fixture 断网 → 退化为目录子集（契约的一部分）。
    """
    _clear_provider_credentials(monkeypatch)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")

    opts = config_manager.options()
    knobs = {k["key"]: k for k in opts["knobs"]}
    values = [o["value"] for o in knobs["personaModel"]["options"]]

    assert values == ["deepseek/deepseek-v4-pro", "deepseek/deepseek-flash"]
    # 默认值必须落在可选集合内，否则每次运行都会因缺 key 失败
    assert opts["environment"]["personaModel"] in values
    assert opts["environment"]["personaModel"] == "deepseek/deepseek-v4-pro"

    # 加上 DashScope 凭据后，其模型回到列表里
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-test")
    values = [
        o["value"]
        for o in {k["key"]: k for k in config_manager.options()["knobs"]}["personaModel"]["options"]
    ]
    assert "dashscope/deepseek-v4-pro" in values
    assert all(v.split("/", 1)[0] in {"deepseek", "dashscope"} for v in values)


def test_persona_model_default_falls_back_to_available(monkeypatch):
    _clear_provider_credentials(monkeypatch)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    # 产品默认（Anthropic）无凭据 → 退到第一个可用模型
    assert persona_model() == "deepseek/deepseek-v4-pro"

    # 显式配置优先：便于先挑模型再补 key（preflight 会报缺凭据）
    monkeypatch.setenv(PERSONA_MODEL_ENV, "anthropic/claude-opus-4-8")
    assert persona_model() == "anthropic/claude-opus-4-8"

    # 什么都没配 → 保留产品默认
    _clear_provider_credentials(monkeypatch)
    assert persona_model() == "anthropic/claude-haiku-4-5"


def test_preflight_recognizes_openrouter_credentials(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_API_KEY", raising=False)
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("ZAI_API_KEY", raising=False)

    body = client.get("/api/preflight").json()
    model = next(c for c in body["checks"] if c["name"] == "Model credentials")
    assert model["ok"] is False

    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    body = client.get("/api/preflight").json()
    model = next(c for c in body["checks"] if c["name"] == "Model credentials")
    openrouter = next(c for c in body["checks"] if c["name"] == "OpenRouter")
    assert model["ok"] is True
    assert "OpenRouter" in model["detail"]
    assert openrouter["ok"] is True
    assert openrouter.get("optional") is True


def test_options_rebuilds_agent_flag(config_manager):
    knobs = {k["key"]: k for k in config_manager.options()["knobs"]}
    # Every editable knob feeds the bridge's agent cache key, so each one
    # rebuilds (re-warms) the agent when changed — including botType, which is
    # part of INTERECAGENT_BOT_TYPE in the agent cache key.
    assert knobs["applicationId"]["rebuildsAgent"] is True
    assert knobs["domain"]["rebuildsAgent"] is True
    assert knobs["botType"]["rebuildsAgent"] is True
    assert knobs["engine"]["rebuildsAgent"] is True
    assert knobs["personaModel"]["rebuildsAgent"] is False


def test_bottype_change_requires_rebuild(config_manager):
    # Changing only botType must invalidate the cached agent (cold start),
    # because the bridge folds INTERECAGENT_BOT_TYPE into its agent cache key.
    old = {"botType": "chat"}
    new = {"botType": "completion"}
    assert config_manager.cache_invalidating(old, new) is True
    # botType is enumerated among the cache-invalidating keys.
    assert "botType" in config_manager.CACHE_INVALIDATING_KEYS
    # Sanity: an unchanged config does not force a rebuild.
    assert config_manager.cache_invalidating(old, dict(old)) is False


def test_options_defaults_are_full_config(config_manager):
    defaults = config_manager.options()["defaults"]
    # Full config: every key, including the fixed ranker/resource modes.
    assert set(defaults.keys()) == {
        "applicationId",
        "engine",
        "rankerMode",
        "resourceMode",
        "domain",
        "botType",
    }
    assert defaults["applicationId"] == "meal_planning_nutrition"
    assert defaults["engine"] == "gpt-4o-mini"
    assert defaults["domain"] == "movie"


def test_options_environment_block(config_manager, monkeypatch):
    _clear_provider_credentials(monkeypatch)
    env = config_manager.options()["environment"]
    assert set(env.keys()) == {
        "runtime",
        "personaAgent",
        "personaModel",
        "applicationApi",
        "scorer",
        "cache",
        "ranker",
        "resources",
        "agent",
        "promptOwnership",
        "executionPlane",
        "remoteRunnerConfigured",
        "computeFamily",
        "computeFamilies",
    }
    assert env["runtime"] == "In-process Harbor runner"
    assert env["personaAgent"] == "Playground simulated user"
    assert env["personaModel"] == "anthropic/claude-haiku-4-5"
    assert env["applicationApi"] == "direct application adapter"
    assert env["scorer"] == "Playground self-report scorer"
    assert env["cache"] == "local service and model caches"
    assert "application-specific" in env["ranker"]
    assert "adapter-specific" in env["resources"]
    assert "chatbot application adapter" in env["agent"]
    assert env["promptOwnership"] == {
        "personaSystemPrompt": "Persona prompt from Playground",
        "taskPrompt": "Application-provided chatbot simulation prompt",
    }
