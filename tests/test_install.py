import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PLUGIN = Path(__file__).resolve().parents[1]


class InstallTests(unittest.TestCase):
    def test_install_preserves_existing_settings_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory)
            shell = config / "omarchy/shell.json"
            shell.parent.mkdir()
            original = {"bar": {"position": "top", "layout": {"centerBegin": [{"id": "old.widget"}],
                        "center": [{"id": "omarchy.clock", "format": "HH:mm"}]}},
                        "plugins": [{"id": "old.plugin"}], "idle": {"lock": 300}}
            shell.write_text(json.dumps(original))
            env = dict(os.environ, XDG_CONFIG_HOME=directory)
            command = [sys.executable, str(PLUGIN / "install.py")]
            first = subprocess.run(command, env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(first.returncode, 0, first.stderr)
            after = json.loads(shell.read_text())
            self.assertEqual(after["bar"]["layout"]["centerBegin"], [{"id": "old.widget"}, {"id": "max.pomodoro"}])
            self.assertEqual(after["bar"]["layout"]["center"], original["bar"]["layout"]["center"])
            self.assertEqual(after["plugins"], [{"id": "old.plugin"}, {"id": "max.pomodoro"}])
            self.assertEqual(after["idle"], original["idle"])
            durations = config / "pomodoro/config.json"
            durations.write_text('{"work_minutes":40,"break_minutes":10}')
            second = subprocess.run(command, env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(json.loads(shell.read_text()), after)
            self.assertEqual(json.loads(durations.read_text())["work_minutes"], 40)
            self.assertEqual(len(list(shell.parent.glob("shell.json.before-pomodoro-*"))), 1)


if __name__ == "__main__":
    unittest.main()
