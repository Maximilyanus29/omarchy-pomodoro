#!/usr/bin/env python3
"""Session-local Pomodoro clock. JSON lines on stdin/stdout; no third-party modules."""

import argparse
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import selectors
import sys
import tempfile
import time

DEFAULTS = {"work_minutes": 25, "break_minutes": 5}


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".pomo-")
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class Clock:
    def __init__(self, config, state, session, now=time.monotonic):
        self.config_path, self.state_path = Path(config), Path(state)
        self.session, self.now = session, now
        self.config = dict(DEFAULTS)
        self.error = ""
        self.phase, self.status = "work", "off"
        self.remaining, self.deadline = 1500.0, None
        self.alert = False
        self.serial = 0
        self.load_config()
        self.remaining = self.duration()
        self.restore()
        self.tick()
        self.initialized = True

    def load_config(self):
        previous = self.config
        try:
            raw = json.loads(self.config_path.read_text())
            if not isinstance(raw, dict):
                raise ValueError("Expected an object")
            candidate = {key: raw.get(key, default) for key, default in DEFAULTS.items()}
            if any(type(value) is not int or not 1 <= value <= 10080 for value in candidate.values()):
                raise ValueError("Minutes must be integers from 1 to 10080")
            self.config, self.error = candidate, ""
        except FileNotFoundError:
            self.config, self.error = dict(DEFAULTS), ""
        except (OSError, ValueError, OverflowError):
            self.error = "config"
        if self.status == "off":
            self.remaining = self.duration()
        if self.config != previous and getattr(self, "initialized", False):
            self.save()

    def duration(self):
        return self.config["work_minutes" if self.phase == "work" else "break_minutes"] * 60.0

    def restore(self):
        try:
            data = json.loads(self.state_path.read_text())
            if not isinstance(data, dict):
                return
            if data.get("session") != self.session or data.get("version") != 1:
                return
            phase, status = data["phase"], data["status"]
            if phase not in ("work", "break") or status not in ("off", "running", "paused", "ready"):
                return
            remaining = float(data["remaining"])
            deadline = float(data["deadline"]) if status == "running" else None
            if not math.isfinite(remaining) or not 0 <= remaining <= 604800:
                return
            if deadline is not None and (not math.isfinite(deadline) or deadline > self.now() + 604800):
                return
            cached = data.get("config", {})
            if self.error and all(type(cached.get(key)) is int and 1 <= cached[key] <= 10080 for key in DEFAULTS):
                self.config = cached
            self.phase, self.status = phase, status
            self.remaining, self.deadline = remaining, deadline
            self.alert = data.get("alert") is True and status == "ready"
            self.serial = max(0, int(data.get("serial", 0)))
        except (OSError, ValueError, KeyError, TypeError, OverflowError):
            return

    def save(self):
        atomic_json(self.state_path, {
            "version": 1, "session": self.session, "phase": self.phase,
            "status": self.status, "remaining": self.remaining, "deadline": self.deadline,
            "alert": self.alert, "serial": self.serial, "config": self.config,
        })

    def tick(self):
        if self.status != "running":
            return
        self.remaining = max(0.0, self.deadline - self.now())
        if self.remaining == 0:
            self.phase = "break" if self.phase == "work" else "work"
            self.status, self.deadline = "ready", None
            self.remaining, self.alert = self.duration(), True
            self.serial += 1
            self.save()

    def command(self, action):
        self.load_config()
        self.tick()
        if action == "enable" and self.status == "off":
            self.phase, self.status = "work", "running"
            self.remaining, self.alert = self.duration(), False
            self.deadline = self.now() + self.remaining
        elif action == "start" and self.status in ("ready", "paused"):
            self.status, self.alert = "running", False
            self.deadline = self.now() + self.remaining
        elif action == "pause" and self.status == "running":
            self.status, self.deadline = "paused", None
        elif action == "reset" and self.status != "off":
            self.status, self.deadline, self.alert = "paused", None, False
            self.remaining = self.duration()
        elif action == "disable":
            self.phase, self.status = "work", "off"
            self.remaining, self.deadline, self.alert = self.duration(), None, False
        elif action == "dismiss":
            self.alert = False
        elif action != "status":
            return
        self.save()

    def snapshot(self):
        return {"phase": self.phase, "status": self.status,
                "seconds": math.ceil(self.remaining), "alert": self.alert,
                "serial": self.serial, "error": self.error, "config": self.config}


def session_key():
    # The compositor signature changes at login, while shell reloads keep it.
    identity = "|".join(os.environ.get(key, "") for key in
                        ("XDG_SESSION_ID", "HYPRLAND_INSTANCE_SIGNATURE", "WAYLAND_DISPLAY"))
    identity += Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    return hashlib.sha256(identity.encode()).hexdigest()[:24]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    parser.add_argument("--config", type=Path, default=config_home / "pomodoro/config.json")
    parser.add_argument("--state", type=Path)
    args = parser.parse_args()
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if args.state is None and not runtime:
        parser.error("XDG_RUNTIME_DIR is required")
    session = session_key()
    state = args.state or Path(runtime) / "max.pomodoro" / (session + ".json")
    state.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with state.with_suffix(".lock").open("w") as lock:
        # An old shell may still be closing its pipes during a hot reload.
        until = time.monotonic() + 3
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= until:
                    raise RuntimeError("Another Pomodoro clock owns this session")
                time.sleep(0.05)
        clock = Clock(args.config, state, session)
        selector = selectors.DefaultSelector()
        selector.register(sys.stdin, selectors.EVENT_READ)
        pending, last, config_check = b"", None, 0.0
        while True:
            now = time.monotonic()
            if now >= config_check:
                clock.load_config()
                config_check = now + 1
            clock.tick()
            current = json.dumps(clock.snapshot(), sort_keys=True)
            if current != last:
                print(current, flush=True)
                last = current
            if not selector.select(0.2):
                continue
            chunk = os.read(sys.stdin.fileno(), 4096)
            if not chunk:
                break
            pending += chunk
            if len(pending) > 65536:
                raise ValueError("Command exceeds size limit")
            while b"\n" in pending:
                line, pending = pending.split(b"\n", 1)
                try:
                    command = json.loads(line)
                    if isinstance(command, dict):
                        clock.command(command.get("action"))
                except (ValueError, UnicodeDecodeError):
                    print("Ignoring malformed command", file=sys.stderr)
        selector.close()


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError) as error:
        print(f"Pomodoro backend: {error}", file=sys.stderr)
        sys.exit(1)
