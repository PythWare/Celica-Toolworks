from __future__ import annotations
import json
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent / "celica_config.json"
GAME_ROOT_KEY = "game_root"
cache = {"stamp": None, "data": {}}

def load():
    try:
        stamp = CONFIG_PATH.stat().st_mtime_ns
    except OSError:
        cache["stamp"] = None
        cache["data"] = {}
        return {}

    if cache["stamp"] == stamp:
        return cache["data"]

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        data = {}

    if not isinstance(data, dict):
        data = {}

    cache["stamp"] = stamp
    cache["data"] = data
    return data

def save(data):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
            handle.write("\n")
    except OSError:
        return False

    cache["stamp"] = None
    cache["data"] = {}
    return True

def get_game_root():
    value = load().get(GAME_ROOT_KEY)
    if not value:
        return None

    candidate = Path(value)
    if not candidate.is_dir():
        return None
    return candidate

def set_game_root(path):
    data = dict(load())
    data[GAME_ROOT_KEY] = str(Path(path))
    return save(data)

def clear_game_root():
    data = dict(load())
    data.pop(GAME_ROOT_KEY, None)
    return save(data)
