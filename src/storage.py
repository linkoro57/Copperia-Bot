import json
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
STATE_PATH = DATA_DIR / "state.json"

DEFAULT_STATE = {
    "sent_panels": {
        "regulation": False,
        "anti_scam": False,
        "tickets": False,
    },
    "tickets": {
        "counter": 0,
        "channels": {},
    },
    "temp_bans": [],
}


def _deep_merge(base, incoming):
    if isinstance(base, dict) and isinstance(incoming, dict):
        merged = dict(base)
        for key, value in incoming.items():
            merged[key] = _deep_merge(base.get(key), value)
        return merged
    return incoming if incoming is not None else base


def ensure_storage():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not STATE_PATH.exists():
        STATE_PATH.write_text(json.dumps(DEFAULT_STATE, indent=2), encoding="utf-8")


def read_state():
    ensure_storage()
    raw = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return _deep_merge(DEFAULT_STATE, raw)


def write_state(state):
    ensure_storage()
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
