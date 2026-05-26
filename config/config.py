import os

import yaml

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.yaml")


with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f) or {}

# Runtime-safe defaults for stateless frontend mode.
cfg.setdefault("proxy", None)
cfg.setdefault("BOT_TOKEN", "")

cfg.setdefault("AD", {})
cfg["AD"].setdefault("text", "")
cfg["AD"].setdefault("url", "")

cfg.setdefault("NEW_SERVICE", {})
cfg["NEW_SERVICE"].setdefault("base_url", "http://127.0.0.1:8080")
