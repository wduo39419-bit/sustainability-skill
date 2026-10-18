"""Tests use invented values only, never project research data."""
import hashlib
from http.server import ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen, Request

MODULE = Path(__file__).resolve().parents[1] / 'progress_view.py'
spec = importlib.util.spec_from_file_location('progress_view', MODULE)
view = importlib.util.module_from_spec(spec)
spec.loader.exec_module(view)


class ProgressTests(unittest.TestCase):
    def test_log_parser(self):
        result = view.parse_log('Time = 8\nGAMG: Solving for p, Initial residual = 0.03, Final residual = 2e-08, No Iterations 9\ntime step continuity errors : sum local = 1e-07, global = -2e-09, cumulative = 3e-08\nEnd\n')
        self.assertEqual(result['coordinate'], 8)
        self.assertEqual(result['residuals']['p']['linear_iterations'], 9)
        self.assertEqual(result['residuals']['p']['coordinate'], 8)
        self.assertEqual(result['continuity']['global'], -2e-9)
        self.assertTrue(result['ended'])

    def test_partial_next_step_retains_residual_coordinate(self):
        result = view.parse_log('Time = 1.5\nDILUPBiCGStab: Solving for Ux, Initial residual = 0.01, Final residual = 1e-09, No Iterations 2\nTime = 1.6\n')
        self.assertEqual(result['coordinate'], 1.6)
        self.assertEqual(result['residuals']['Ux']['coordinate'], 1.5)

    def test_missing_is_not_zero(self):
        result = view.normalize_rows({'snapshots': [{'iteration': 10}]}, 60)[0]
        self.assertIsNone(result['tau95_Pa'])
        self.assertIsNone(result['source_force_N'])
        self.assertIsNone(result['momentum_gap_relative'])
        self.assertEqual(view.percentage(None), '—')

    def test_percent_and_alias_fields(self):
        row = view.normalize_rows({'rows': [{'iteration': 4, 'tau_max_Pa': .3, 'force_N': 80, 'momentum_gap_percent': 5}]}, 10)[0]
        self.assertEqual(row['taumax_Pa'], .3)
        self.assertEqual(row['source_force_N'], 80)
        self.assertEqual(row['momentum_gap_relative'], .05)

    def test_sort_deduplicate_and_limit(self):
        rows = view.normalize_rows({'snapshots': [{'iteration': 2}, {'iteration': 1}, {'iteration': 2, 'tau95_Pa': .6}, {'iteration': 3}]}, 2)
        self.assertEqual([r['iteration'] for r in rows], [2, 3])
        self.assertEqual(rows[0]['tau95_Pa'], .6)

    def test_nonfinite_not_rendered_as_measurements(self):
        self.assertIsNone(view.number(float('nan')))
        self.assertIsNone(view.number(float('inf')))
        self.assertIsNone(view.number(True))
        self.assertIsNone(view.relative_change(None, 1))
        self.assertEqual(view.relative_change(0, 0), 0)

    def test_fatal_log_marker_is_visible(self):
        self.assertTrue(view.parse_log('FOAM FATAL ERROR')['fatal_marker'])

    def test_demo_is_labeled_and_not_accepted(self):
        config = view.load_config(['--demo'])
        data = view.snapshot(config)
        page = view.render(data, config)
        self.assertIn('虚构演示', page)
        self.assertIn('预算使用比例不代表收敛程度', page)
        self.assertIn('虚构数据，不作验收', page)
        self.assertFalse(any('pass' in value.lower() for value in data['acceptance'].values()))

    def test_user_text_is_escaped(self):
        config = view.load_config(['--demo', '--title', '<script>alert(1)</script>'])
        page = view.render(view.snapshot(config), config)
        self.assertNotIn('<script>', page)
        self.assertIn('&lt;script&gt;', page)

    def test_inputs_are_read_only_and_paths_not_exposed(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / 'status.json'
            log = Path(directory) / 'log.simpleFoam'
            state.write_text(json.dumps({'snapshots': [{'iteration': 4}], 'acceptance': {'overall': '未判定'}}))
            log.write_text('Time = 6\n')
            before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in [state, log]}
            config = view.load_config(['--status', str(state), '--log', str(log), '--budget', '10'])
            data = view.snapshot(config)
            self.assertEqual(data['budget_used_percent'], 60)
            self.assertNotIn(directory, json.dumps(data))
            self.assertEqual(before, {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in [state, log]})

    def test_invalid_state_has_warning_and_no_path(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'status.json'
            path.write_text('{unfinished')
            state, stamp, error = view.read_state(path)
            self.assertEqual(state, {})
            self.assertIsNone(stamp)
            self.assertNotIn(directory, error)

    def test_config_paths_are_portable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            path.write_text(json.dumps({'log': 'local/example.log'}))
            config = view.load_config(['--config', str(path)])
            self.assertEqual(config['log_path'], Path(directory, 'local', 'example.log'))

    def test_restarted_log_does_not_inherit_future_progress(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / 'status.json'
            log = Path(directory) / 'log.simpleFoam'
            state.write_text(json.dumps({'snapshots': [{'iteration': 80}]}))
            log.write_text('Time = 10\n')
            config = view.load_config(['--status', str(state), '--log', str(log), '--budget', '100'])
            data = view.snapshot(config)
            self.assertEqual(data['current'], 10)
            self.assertTrue(any('不同运行' in warning for warning in data['warnings']))


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = view.load_config(['--demo'])
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), view.handler_for(cls.config))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def test_home_and_api(self):
        with urlopen(self.base) as response:
            self.assertEqual(response.status, 200)
            self.assertIn('no-store', response.headers['Cache-Control'])
            self.assertIn('虚构演示', response.read().decode('utf-8'))
        with urlopen(self.base + '/api/status') as response:
            self.assertTrue(json.loads(response.read())['demo'])

    def test_health(self):
        with urlopen(self.base + '/health') as response:
            self.assertEqual(json.loads(response.read()), {'ok': True, 'read_only': True})

    def test_arbitrary_file_routes_not_exposed(self):
        with self.assertRaises(HTTPError) as error:
            urlopen(self.base + '/progress_view.py')
        self.assertEqual(error.exception.code, 404)

    def test_post_cannot_mutate_state(self):
        with self.assertRaises(HTTPError) as error:
            urlopen(Request(self.base + '/', data=b'{}', method='POST'))
        self.assertEqual(error.exception.code, 501)


if __name__ == '__main__':
    unittest.main()
