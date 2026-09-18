"""Tests for :mod:`backend.service.persona_model_discovery`.

全部离线：HTTP 边界（``urllib.request.urlopen``）被 stub 成给定 payload，
另有 conftest 的 autouse fixture 保证其它用例根本不发网络请求。
"""

from __future__ import annotations

import json
import urllib.error
from typing import Any, Dict, List

import pytest

from backend.service import persona_model_discovery as discovery
from backend.service.config import (
    HARBOR_PERSONA_MODEL_ENV,
    PERSONA_MODEL_ENV,
    PERSONA_MODEL_PROVIDER_KEYS,
    available_persona_models,
    persona_model_label,
)


class _FakeResponse:
    def __init__(self, payload: Dict[str, Any]) -> None:
        self._body = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc: Any) -> bool:
        return False


def _clear_provider_credentials(monkeypatch) -> None:
    for env_names in PERSONA_MODEL_PROVIDER_KEYS.values():
        for name in env_names:
            monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv(PERSONA_MODEL_ENV, raising=False)
    monkeypatch.delenv(HARBOR_PERSONA_MODEL_ENV, raising=False)


@pytest.fixture()
def http(monkeypatch):
    """记录请求；默认返回两个 DeepSeek id（与官方账号实际一致）。"""
    calls: List[Dict[str, Any]] = []

    def fake_urlopen(request, timeout=None):
        calls.append(
            {
                "url": request.full_url,
                "auth": request.headers.get("Authorization"),
                "timeout": timeout,
            }
        )
        return _FakeResponse({"data": [{"id": "deepseek-v4-pro"}, {"id": "deepseek-flash"}]})

    monkeypatch.setattr(discovery.urllib.request, "urlopen", fake_urlopen)
    discovery.clear_cache()
    return calls


def test_discover_reads_models_endpoint_and_caches(http, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")

    assert discovery.discover("deepseek") == ["deepseek-v4-pro", "deepseek-flash"]
    assert http[0]["url"] == "https://api.deepseek.com/v1/models"
    assert http[0]["auth"] == "Bearer sk-test"

    # 命中缓存：第二次不再发请求
    assert discovery.discover("deepseek") == ["deepseek-v4-pro", "deepseek-flash"]
    assert len(http) == 1


def test_discover_honours_base_url_override(http, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("DEEPSEEK_API_BASE", "https://example.test/v9/")

    discovery.discover("deepseek")

    assert http[0]["url"] == "https://example.test/v9/models"


def test_discover_degrades_without_raising(monkeypatch):
    def boom(*args, **kwargs):
        raise urllib.error.URLError("no route to host")

    monkeypatch.setattr(discovery.urllib.request, "urlopen", boom)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    discovery.clear_cache()
    calls = []
    monkeypatch.setattr(
        discovery.urllib.request,
        "urlopen",
        lambda *a, **k: (calls.append(1), boom())[1],
    )

    assert discovery.discover("deepseek") == []
    # 失败也进缓存（短 TTL），避免每次请求都打网络
    assert discovery.discover("deepseek") == []
    assert len(calls) == 1


def test_provider_without_models_endpoint_is_not_probed(http, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

    assert discovery.discover("anthropic") == []
    assert http == []


def test_available_persona_models_merges_discovered_ids(http, monkeypatch):
    _clear_provider_credentials(monkeypatch)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    # 该账号多了一个目录里没有的新模型
    monkeypatch.setattr(
        discovery.urllib.request,
        "urlopen",
        lambda request, timeout=None: _FakeResponse(
            {"data": [{"id": "deepseek-v5-pro"}, {"id": "deepseek-flash"}]}
        ),
    )
    discovery.clear_cache()

    models = available_persona_models()

    # 目录已知的排在前（保留人工标签与顺序），发现到的新模型追加在后
    assert models == ["deepseek/deepseek-flash", "deepseek/deepseek-v5-pro"]
    assert persona_model_label("deepseek/deepseek-flash") == "DeepSeek V4 Flash"
    # 目录外的模型不猜产品名，直接显示 id
    assert persona_model_label("deepseek/deepseek-v5-pro") == "deepseek/deepseek-v5-pro"


def test_unconfigured_deployment_keeps_full_catalog_without_probing(http, monkeypatch):
    _clear_provider_credentials(monkeypatch)

    models = available_persona_models()

    assert len(models) > 2
    assert "anthropic/claude-haiku-4-5" in models
    assert http == []
