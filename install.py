#!/usr/bin/env python3
"""Install the user plugin without replacing unrelated shell settings."""
import datetime
import json
import os
from pathlib import Path
import shutil
from timer import atomic_json


def main():
    source = Path(__file__).resolve().parent
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    shell = config_home / "omarchy/shell.json"
    config = json.loads(shell.read_text())
    layout = config.setdefault("bar", {}).setdefault("layout", {})
    entries = [entry for section in layout.values() if isinstance(section, list) for entry in section]
    if not any(isinstance(entry, dict) and entry.get("id") == "max.pomodoro" for entry in entries):
        layout.setdefault("centerBegin", []).append({"id": "max.pomodoro"})
    plugins = config.setdefault("plugins", [])
    if not any((entry.get("id") if isinstance(entry, dict) else entry) == "max.pomodoro" for entry in plugins):
        plugins.append({"id": "max.pomodoro"})
    if "disabledPlugins" in config:
        config["disabledPlugins"] = [entry for entry in config["disabledPlugins"] if entry != "max.pomodoro"]
    destination = config_home / "omarchy/plugins/max.pomodoro"
    if source != destination:
        shutil.copytree(source, destination, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    durations = config_home / "pomodoro/config.json"
    if not durations.exists():
        atomic_json(durations, {"work_minutes": 25, "break_minutes": 5})
    if config != json.loads(shell.read_text()):
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup = shell.with_name("shell.json.before-pomodoro-" + stamp)
        shutil.copy2(shell, backup)
        # Keep the existing formatting style for easy manual review.
        atomic_json(shell, config)
        print(f"Shell configuration backup: {backup}")
    print(f"Plugin: {destination}")
    print(f"Durations: {durations}")


if __name__ == "__main__":
    main()
