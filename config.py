"""
配置加载器 —— 读取 config.yaml，提供全局配置对象。
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


@lru_cache(maxsize=1)
def load_config(config_path: str = "") -> dict:
    path = Path(config_path) if config_path else Path(__file__).parent / "config.yaml"
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    # 将环境变量注入 llm.api_key
    api_key_env = cfg.get("llm", {}).get("api_key_env", "LLM_API_KEY")
    cfg.setdefault("llm", {})["api_key"] = os.getenv(api_key_env, "")
    return cfg


def get(section: str, key: str, default: Any = None) -> Any:
    cfg = load_config()
    return cfg.get(section, {}).get(key, default)
