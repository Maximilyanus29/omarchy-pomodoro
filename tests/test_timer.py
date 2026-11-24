import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "timer.py"
spec = importlib.util.spec_from_file_location("pomodoro_timer", SOURCE)
timer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(timer)


class ClockTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.config = self.directory / "config.json"
        self.state = self.directory / "state.json"
        self.elapsed = 1000.0
        self.clock = self.create()

    def create(self, session="test"):
        return timer.Clock(self.config, self.state, session, lambda: self.elapsed)

    def advance(self, seconds):
        self.elapsed += seconds
        self.clock.tick()

    def configure(self, work=25, rest=5):
        self.config.write_text(json.dumps({"work_minutes": work, "break_minutes": rest}))
        self.clock.load_config()

    def test_disabled_on_first_launch(self):
        self.assertEqual(self.clock.snapshot()["status"], "off")
        self.assertEqual(self.clock.snapshot()["seconds"], 1500)

    def test_full_cycle_waits_for_manual_start(self):
        self.clock.command("enable")
        self.advance(1500)
        self.assertEqual((self.clock.phase, self.clock.status, self.clock.remaining), ("break", "ready", 300))
        self.assertTrue(self.clock.alert)
        self.advance(5000)
        self.assertEqual(self.clock.remaining, 300)
        self.clock.command("dismiss")
        self.assertFalse(self.clock.alert)
        self.assertEqual(self.clock.status, "ready")
        self.clock.command("start")
        self.advance(300)
        self.assertEqual((self.clock.phase, self.clock.status, self.clock.remaining), ("work", "ready", 1500))
        self.assertEqual(self.clock.serial, 2)

    def test_pause_and_resume_preserve_fraction(self):
        self.clock.command("enable")
        self.advance(12.25)
        self.clock.command("pause")
        self.advance(8000)
        self.assertEqual(self.clock.remaining, 1487.75)
        self.clock.command("start")
        self.advance(0.75)
        self.assertEqual(self.clock.remaining, 1487)

    def test_reset_current_phase_and_disable(self):
        self.clock.command("enable")
        self.advance(1500)
        self.clock.command("start")
        self.advance(10)
        self.clock.command("reset")
        self.assertEqual((self.clock.phase, self.clock.status, self.clock.remaining), ("break", "paused", 300))
        self.clock.command("disable")
        self.assertEqual((self.clock.phase, self.clock.status, self.clock.remaining), ("work", "off", 1500))

    def test_clock_reload_does_not_reset_running_deadline(self):
        self.clock.command("enable")
        self.advance(73)
        restored = self.create()
        self.assertEqual((restored.status, restored.remaining), ("running", 1427))
        self.assertEqual(restored.deadline, self.clock.deadline)

    def test_restore_expired_clock_moves_only_one_stage(self):
        self.clock.command("enable")
        self.elapsed += 50000
        restored = self.create()
        self.assertEqual((restored.phase, restored.status, restored.remaining), ("break", "ready", 300))

    def test_reload_paused_and_pending_alert(self):
        self.clock.command("enable")
        self.advance(7)
        self.clock.command("pause")
        self.assertEqual((self.create().status, self.create().remaining), ("paused", 1493))
        self.clock.command("start")
        self.advance(1493)
        self.assertTrue(self.create().alert)
        self.clock.command("dismiss")
        self.assertFalse(self.create().alert)

    def test_new_login_starts_disabled(self):
        self.clock.command("enable")
        self.assertEqual(self.create("other-login").status, "off")

    def test_sleep_and_wall_clock_do_not_advance_monotonic_time(self):
        self.clock.command("enable")
        self.advance(20)
        # CLOCK_MONOTONIC stops during suspend; wall time is never read.
        for _ in range(30):
            self.clock.tick()
        self.assertEqual(self.clock.remaining, 1480)
        self.advance(1)
        self.assertEqual(self.clock.remaining, 1479)

    def test_config_applies_to_next_stage_or_reset(self):
        self.clock.command("enable")
        self.advance(100)
        self.configure(30, 7)
        self.assertEqual(self.clock.remaining, 1400)
        self.advance(1400)
        self.assertEqual(self.clock.remaining, 420)
        self.configure(40, 8)
        self.assertEqual(self.clock.remaining, 420)
        self.clock.command("reset")
        self.assertEqual(self.clock.remaining, 480)

    def test_bad_config_keeps_last_valid_across_reload(self):
        self.configure(31, 6)
        self.clock.command("enable")
        for raw in ('{', '[]', '{"work_minutes": 0}', '{"break_minutes": true}', '{"work_minutes": 1.5}', '{"work_minutes": 10081}'):
            self.config.write_text(raw)
            self.clock.load_config()
            self.assertEqual(self.clock.config, {"work_minutes": 31, "break_minutes": 6})
            self.assertEqual(self.clock.error, "config")
        restored = self.create()
        self.assertEqual(restored.config, {"work_minutes": 31, "break_minutes": 6})
        self.assertEqual(restored.remaining, 1860)
        self.configure()
        self.assertEqual(self.clock.error, "")

    def test_bad_state_ignored(self):
        for raw in ('{', '[]', '{"version": 1, "session": "test", "phase": "work", "status": "running", "remaining": "nan", "deadline": 12}'):
            self.state.write_text(raw)
            self.assertEqual(self.create().status, "off")

    def test_repeated_enable_and_start_do_not_reset(self):
        self.clock.command("enable")
        self.advance(123)
        self.clock.command("enable")
        self.clock.command("start")
        self.assertEqual(self.clock.remaining, 1377)

    def test_process_handles_batched_commands_and_malformed_input(self):
        result = subprocess.run(
            [sys.executable, str(SOURCE), "--config", str(self.config), "--state", str(self.state)],
            input='invalid\n{"action":"enable"}\n{"action":"pause"}\n',
            text=True, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        snapshots = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(snapshots[-1]["status"], "paused")
        self.assertIn("malformed", result.stderr)


if __name__ == "__main__":
    unittest.main()
