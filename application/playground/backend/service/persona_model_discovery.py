"""发现本部署真正可调用的 persona 模型。

对每个已配置凭据的 provider 请求其 OpenAI 兼容的 ``{base}/models``（与 runner
用的同一批 base URL，可用 ``<PROVIDER>_API_BASE`` 覆盖），把返回的 id 与
:mod:`backend.service.config` 里的静态目录合并 —— 目录提供人工审核过的标签/描述
与顺序，目录里没有的新模型追加在后面，这样厂商发新模型不用改代码。

任何失败（无网络、key 无效、返回结构异常）都不抛错，只是退化为该 provider 的
目录子集：发现失败绝不能让模型下拉框不可用。
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
from typing import Dict, Iterable, List, Tuple

from .config import PERSONA_MODEL_PROVIDER_KEYS

#: provider → (base URL 覆盖用的环境变量, 默认 OpenAI 兼容 base)。
#: ``anthropic`` 不在此表：Claude 没有 OpenAI 兼容 base，其选项仍全部来自静态目录。
MODEL_LIST_BASES: Dict[str, Tuple[str, str]] = {
    "openai": ("OPENAI_API_BASE", "https://api.openai.com/v1"),
    "deepseek": ("DEEPSEEK_API_BASE", "https://api.deepseek.com/v1"),
    "xai": ("XAI_API_BASE", "https://api.x.ai/v1"),
    "dashscope": (
        "DASHSCOPE_API_BASE",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    ),
    "zai": ("ZAI_API_BASE", "https://open.bigmodel.cn/api/paas/v4"),
    "openrouter": ("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1"),
    "gemini": (
        "GEMINI_API_BASE",
        "https://generativelanguage.googleapis.com/v1beta/openai",
    ),
}

#: 缓存 TTL（秒）。成功的发现结果按此缓存；失败只缓存很短时间，方便补 key 后尽快生效。
CACHE_TTL_ENV = "PERSONA_MODEL_DISCOVERY_TTL"
DEFAULT_CACHE_TTL = 300.0
FAILURE_CACHE_TTL = 30.0
DEFAULT_TIMEOUT = 5.0

_cache: Dict[str, Tuple[float, List[str]]] = {}


def _ttl() -> float:
    raw = (os.environ.get(CACHE_TTL_ENV) or "").strip()
    try:
        return max(0.0, float(raw)) if raw else DEFAULT_CACHE_TTL
    except ValueError:
        return DEFAULT_CACHE_TTL


def _api_key(provider: str) -> str:
    for name in PERSONA_MODEL_PROVIDER_KEYS.get(provider, ()):
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    return ""


def _base_url(provider: str) -> str:
    env_name, default = MODEL_LIST_BASES[provider]
    return (os.environ.get(env_name) or default).strip().rstrip("/")


def _fetch_ids(provider: str, timeout: float) -> List[str]:
    """请求 ``{base}/models`` 并返回裸模型 id；结构不符时返回空列表。"""
    request = urllib.request.Request(
        "{}/models".format(_base_url(provider)),
        headers={
            "Authorization": "Bearer {}".format(_api_key(provider)),
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    entries = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return []
    ids: List[str] = []
    for entry in entries:
        model_id = entry.get("id") if isinstance(entry, dict) else None
        if isinstance(model_id, str) and model_id.strip():
            ids.append(model_id.strip())
    return ids


def discover(
    provider: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    use_cache: bool = True,
) -> List[str]:
    """该 provider 当前可用的**裸**模型 id（不含 ``provider/`` 前缀）。

    已知不可用的 provider（无 OpenAI 兼容 base）与任何请求失败都返回空列表。
    """
    if provider not in MODEL_LIST_BASES:
        return []
    now = time.monotonic()
    if use_cache:
        cached = _cache.get(provider)
        if cached and cached[0] > now:
            return list(cached[1])
    try:
        ids = _fetch_ids(provider, timeout)
    except Exception:  # noqa: BLE001 — 发现失败只降级，不向 UI 抛错
        ids = []
    _cache[provider] = (now + (_ttl() if ids else FAILURE_CACHE_TTL), ids)
    return list(ids)


def discovered_models(
    providers: Iterable[str],
    *,
    timeout: float = DEFAULT_TIMEOUT,
) -> Dict[str, List[str]]:
    """{provider: [裸 id, ...]}，只保留真正列出模型的 provider。"""
    found: Dict[str, List[str]] = {}
    for provider in providers:
        ids = discover(provider, timeout=timeout)
        if ids:
            found[provider] = ids
    return found


def clear_cache() -> None:
    """丢弃缓存的发现结果（配好新 key 或换 base URL 后调用）。"""
    _cache.clear()
