import importlib.util
import json
import os
from pathlib import Path
import pty
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch, Mock
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'skills/robot-ross'), str(ROOT / 'skills/huenit')]
import control_center as ui
import bob_ross as bob
import chat_ross as chat


class PortTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for name in ('JOB_LOCK', 'PENDING_STATE', 'READY_FLAG', 'CALIBRATION_FILE', 'LOG_FILE'):
            p = patch.object(bob, name, str(Path(self.tmp.name) / name))
            p.start()
            self.addCleanup(p.stop)

    def command(self, *args):
        with patch.object(sys, 'argv', ['bob_ross.py', *args]):
            return bob.main()

    def test_ui_positional_shape_size_and_dry_run_never_move(self):
        with patch.object(bob, 'run_draw') as draw, patch.object(bob.subprocess, 'Popen') as spawn:
            self.command('draw', 'circle', '15', '--dry-run')
            draw.assert_not_called()
            spawn.assert_not_called()

    def test_readiness_blocks_motion_before_creating_order(self):
        with patch.object(bob, 'readiness_check', return_value=['not calibrated']), patch.object(bob, 'run_draw') as draw, patch.object(bob.order_log, 'start') as order:
            with self.assertRaises(SystemExit): self.command('write', 'Hello', '--no-voice')
            draw.assert_not_called()
            order.assert_not_called()

    def test_cancel_discards_preview_without_moving(self):
        Path(bob.PENDING_STATE).write_text('{}')
        with patch.object(bob, 'run_draw') as draw:
            self.command('cancel')
            self.assertFalse(Path(bob.PENDING_STATE).exists())
            draw.assert_not_called()

    def test_approve_uses_pending_svg_and_dry_run_does_not_move(self):
        Path(bob.PENDING_STATE).write_text(json.dumps({'svg_path': '/tmp/example.svg', 'prompt': 'tree'}))
        with patch.object(bob, 'run_draw') as draw:
            self.command('approve', '--dry-run')
            draw.assert_not_called()

    def test_sketch_must_succeed_and_non_direct_produces_preview(self):
        def generate(args, **kwargs):
            Path(args[args.index('--out') + 1]).write_text('<svg/>')
            return Mock(returncode=0)
        with patch.object(bob.tempfile, 'gettempdir', return_value=self.tmp.name), patch.object(bob.subprocess, 'run', side_effect=generate), patch.object(bob, 'run_draw') as draw:
            self.command('sketch', 'tree')
            self.assertEqual(json.loads(Path(bob.PENDING_STATE).read_text())['prompt'], 'tree')
            draw.assert_not_called()

    def test_more_photo_detail_recreates_preview(self):
        Path(bob.PENDING_STATE).write_text(json.dumps({'image_path': '/tmp/photo.png', 'smoothness': 6}))
        with patch.object(bob.subprocess, 'run', return_value=Mock(returncode=0)) as runner:
            self.command('more')
            self.assertIn('5', runner.call_args.args[0])
            self.assertEqual(json.loads(Path(bob.PENDING_STATE).read_text())['smoothness'], 5)

    def test_circle_size_is_radius_bounded(self):
        with patch.object(bob.subprocess, 'Popen') as spawn:
            spawn.return_value.returncode = 0
            bob.run_draw('draw', 'circle', 125)
            self.assertEqual(spawn.call_args.args[0][-1], '62.5')

    def test_local_showcase_has_language_prompts_and_imports(self):
        self.assertIn('Respond in French', chat._build_local_system({}, [], None, 'French'))
        self.assertIn('speaking German', chat._build_system({}, [], None, 'German'))

    def test_mac_single_key_reader_and_terminal_restoration(self):
        master, slave = pty.openpty()
        try:
            cmd = [sys.executable, '-c',
                   'import termios,sys; from console_keys import getch; '
                   'old=termios.tcgetattr(0); print("READY",flush=True); '
                   'key=getch(); new=termios.tcgetattr(0); '
                   'old[3] &= ~getattr(termios,"PENDIN",0); new[3] &= ~getattr(termios,"PENDIN",0); '
                   'print("KEY",repr(key),old==new,flush=True)']
            proc = subprocess.Popen(cmd, stdin=slave, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=ROOT / 'skills/huenit')
            self.assertEqual(proc.stdout.readline().strip(), b'READY')
            time.sleep(.1)
            os.write(master, b'q')
            out, err = proc.communicate(timeout=3)
            self.assertEqual(proc.returncode, 0, err)
            self.assertIn(b"KEY b'q' True", out)
        finally:
            os.close(master)
            os.close(slave)


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ui._QuietServer(('127.0.0.1', 0), ui.Handler)
        cls.old_port, ui.PORT = ui.PORT, cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = 'http://127.0.0.1:' + str(ui.PORT)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        ui.PORT = cls.old_port

    def request(self, path, data=None, origin=None):
        headers = {'Content-Type': 'application/json'}
        if origin: headers['Origin'] = origin
        req = urllib.request.Request(self.base + path, data=None if data is None else json.dumps(data).encode(), headers=headers)
        return urllib.request.urlopen(req, timeout=5)

    def test_pages_status_and_svg_catalog(self):
        with self.request('/') as response: self.assertIn(b'Control Center', response.read())
        with self.request('/api/svgs') as response: self.assertTrue(json.load(response)['svgs'])
        with patch.object(ui.Handler, '_check_ollama', return_value=False):
            with self.request('/api/status') as response:
                result = json.load(response)
        self.assertTrue(result['arm_port'].startswith('/dev/cu.'))
        self.assertIn('microphone', result['capabilities'])

    def test_cross_origin_control_denied(self):
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request('/api/execute', {'args': ['draw', 'circle']}, 'https://other.example')
        self.assertEqual(error.exception.code, 403)

    def test_busy_job_returns_conflict(self):
        with patch.object(ui, 'running_job', Mock(is_alive=lambda: True)), patch.object(ui.subprocess, 'Popen') as spawn:
            with self.assertRaises(urllib.error.HTTPError) as error:
                self.request('/api/execute', {'args': ['draw', 'circle']})
            self.assertEqual(error.exception.code, 409)
            spawn.assert_not_called()

    def test_calibration_opens_interactive_mac_terminal_not_arm(self):
        with patch.object(ui.subprocess, 'Popen') as spawn:
            with self.request('/api/calibrate', {}) as response: self.assertTrue(json.load(response)['ok'])
            args = spawn.call_args.args[0]
            self.assertEqual(args[0], 'osascript')
            self.assertIn('do script', args[-1])
            self.assertIn('calibrate', args[-1])


if __name__ == '__main__':
    unittest.main()
