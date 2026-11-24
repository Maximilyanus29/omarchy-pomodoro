#!/usr/bin/env python3
"""Drive real QML buttons and keyboard offscreen, including a live language switch."""
import os
from pathlib import Path
import selectors
import shutil
import subprocess
import sys
import tempfile
import time

plugin = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="pomodoro-ui-") as temporary:
    root = Path(temporary)
    shutil.copytree(plugin, root / "Plugin", ignore=shutil.ignore_patterns(".git", "__pycache__"))
    shutil.copy2(plugin / "tests/ui.qml", root / "shell.qml")
    for name in ("Commons", "Ui"):
        (root / name).symlink_to(Path("/usr/share/omarchy/shell") / name)
    language = root / "config/omarchy/language"
    language.parent.mkdir(parents=True)
    language.write_text("ru\n")
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
               XDG_CONFIG_HOME=str(root / "config"))
    process = subprocess.Popen(["qs", "-p", str(root), "--no-color"], env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        until = time.monotonic() + 20
        pending = b""
        while time.monotonic() < until:
            if not selector.select(0.2):
                if process.poll() is not None:
                    break
                continue
            data = os.read(process.stdout.fileno(), 4096)
            if not data:
                break
            pending += data
            while b"\n" in pending:
                raw, pending = pending.split(b"\n", 1)
                line = raw.decode(errors="replace")
                print(line, flush=True)
                if "QA_AWAIT_ENGLISH" in line:
                    language.write_text("en\n")
        if process.poll() is None:
            process.wait(timeout=2)
        sys.exit(process.returncode)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
