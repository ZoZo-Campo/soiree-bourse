"""Tests sur données fictives uniquement ; tout accès réseau est interdit."""
import copy
import random
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from bourse.database import cents
from bourse.engine import Engine, DEFAULTS, validate_settings
from bourse.storage import Store


class FakeRemote:
    def __init__(self):
        self.prices = {1: 350, 2: 400}
        self.rows, self.writes = [], []
        self.fail_after_commit = False
        self.key = 'fictive'
    def identity(self):
        return self.key
    def catalog(self):
        return [dict(id=i, name=f'Fictive {i}', price=p) for i, p in self.prices.items()]
    def latest_order_id(self):
        return max([100, *(int(row['id']) for row in self.rows)])
    def snapshot(self, ids):
        return {i: self.prices[i] for i in ids}, 100
    def sales(self, baseline, ids):
        return [r for r in self.rows if int(r['id']) > baseline and r['product_id'] in ids]
    def update_prices(self, changes):
        proposed = copy.deepcopy(self.prices)
        for i, old, new in changes:
            if proposed.get(i) not in (old, new):
                raise ValueError('Conflit fictif')
            proposed[i] = new
        self.prices = proposed
        self.writes.append(copy.deepcopy(changes))
        if self.fail_after_commit:
            self.fail_after_commit = False
            raise ConnectionError('Réponse perdue après commit fictif')


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.network = patch.object(socket.socket, 'connect', side_effect=AssertionError('Réseau interdit'))
        self.network.start()
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'fictive.sqlite3'
        self.store = Store(self.path)
        self.remote = FakeRemote()
        self.engine = Engine(self.store, self.remote, rng=random.Random(7))
        self.engine.load_catalog('demo')
    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()
        self.network.stop()
    def prepare_remote(self):
        self.engine.load_catalog('mysql')
        for i in (1, 2):
            self.engine.configure_product(i, dict(cost=100, minimum=150, base=400, maximum=800, selected=True))
        self.engine.start()
    def restart(self):
        self.store.close()
        self.store = Store(self.path)
        self.engine = Engine(self.store, self.remote)

    def test_money_validation(self):
        self.assertEqual(cents('2,345'), 235)
        for value in ('nan', 'inf', '-inf'):
            with self.assertRaises(ValueError):
                cents(value)
        with self.assertRaises(ValueError):
            validate_settings(dict(DEFAULTS, interval=float('nan')))

    def test_fluctuations_dont_fill_reserve_and_respect_bounds(self):
        self.engine.start()
        for _ in range(400):
            self.engine.tick()
            for p in self.engine.selected():
                self.assertLessEqual(p['minimum'], p['price'])
                self.assertLessEqual(p['price'], p['maximum'])
            self.assertEqual(self.engine.snapshot()['reserve'], 0)
        self.assertEqual(self.engine.s['crash_count'], 0)
        self.assertEqual(self.remote.writes, [])

    def test_sale_price_and_cost_are_historical(self):
        self.engine.start()
        p = self.engine.selected()[0]
        price, cost = p['price'], p['cost']
        self.engine.manual_sale(p['id'], 3)
        self.engine.tick()
        self.assertEqual(self.engine.s['revenue'], price * 3)
        self.assertEqual(self.engine.s['cost'], cost * 3)
        self.assertEqual(self.engine.snapshot()['reserve'], (price-cost)*3)
        with self.assertRaises(ValueError):
            self.engine.manual_sale(1, -2)

    def test_crash_threshold_and_manual_only(self):
        self.engine.start()
        with self.assertRaises(ValueError):
            self.engine.crash()
        self.engine.manual_sale(1, 100)
        self.assertTrue(self.engine.snapshot()['can_crash'])
        for _ in range(20):
            self.engine.tick()
        self.assertEqual(self.engine.s['phase'], 'normal')
        self.assertEqual(self.engine.s['crash_count'], 0)
        self.engine.crash()
        self.assertEqual(self.engine.s['phase'], 'crash')
        self.assertFalse(self.engine.snapshot()['can_crash'])
        with self.assertRaises(ValueError):
            self.engine.crash()

    def test_crash_rebound_return(self):
        self.engine.start()
        self.engine.manual_sale(1, 100)
        original = self.engine.selected()[0]['price']
        self.engine.crash()
        self.assertLess(self.engine.selected()[0]['price'], original)
        for _ in range(DEFAULTS['low_ticks']):
            self.engine.tick()
        up = []
        for _ in range(DEFAULTS['rebound_ticks']):
            self.engine.tick()
            up.append(self.engine.selected()[0]['price'])
        self.assertEqual(up, sorted(up))
        self.assertGreater(up[-1], original)
        down = []
        for _ in range(DEFAULTS['recovery_ticks']):
            self.engine.tick()
            down.append(self.engine.selected()[0]['price'])
        self.assertEqual(down, sorted(down, reverse=True))
        self.assertEqual(down[-1], original)
        self.assertEqual(self.engine.s['phase'], 'normal')
        self.assertEqual(self.engine.s['crash_count'], 1)

    def test_fees_and_adjustable_threshold(self):
        self.engine.settings(dict(DEFAULTS, threshold=100, fees=200))
        self.engine.start()
        self.engine.manual_sale(1, 1)
        self.assertFalse(self.engine.snapshot()['can_crash'])
        self.engine.manual_sale(1, 1)
        self.assertTrue(self.engine.snapshot()['can_crash'])
        self.engine.settings(dict(DEFAULTS, threshold=10000, fees=200))
        self.assertFalse(self.engine.snapshot()['can_crash'])

    def test_restore_fresh_original_price_and_only_selected_products(self):
        self.engine.load_catalog('mysql')
        self.engine.configure_product(1, dict(cost=100, minimum=150, base=400, maximum=800, selected=True))
        self.remote.prices[1] = 375
        self.engine.start()
        self.assertEqual(self.remote.prices[1], 400)
        self.assertEqual(self.engine.selected()[0]['original'], 375)
        self.engine.tick()
        self.engine.finish()
        self.assertEqual(self.remote.prices, {1: 375, 2: 400})
        self.assertEqual(self.engine.s['status'], 'closed')
        self.assertFalse(self.engine.due())

    def test_signed_line_total_dedup_and_late_commit(self):
        self.prepare_remote()
        self.remote.rows = [dict(id='103', product_id=1, quantity=3, total=-1050, at='fictive')]
        self.engine.sync_sales()
        self.engine.sync_sales()
        self.assertEqual(self.engine.s['revenue'], 1050)
        self.assertEqual(self.engine.s['cost'], 300)
        self.remote.rows.append(dict(id='102', product_id=2, quantity=1, total=-400, at='fictive'))
        self.engine.sync_sales()
        self.assertEqual(self.engine.s['revenue'], 1450)
        self.assertEqual(self.engine.s['quantity'], 4)
        with self.assertRaises(ValueError):
            self.engine.manual_sale(1, 1)

    def test_sales_since_catalogue_load_are_imported_when_starting(self):
        self.engine.load_catalog('mysql')
        self.engine.configure_product(1, dict(cost=100, minimum=150, base=400, maximum=800, selected=True))
        self.remote.rows.append(dict(id='101', product_id=1, quantity=3, total=-1050, at='fictive'))
        self.engine.start()
        self.assertEqual(self.engine.s['quantity'], 3)
        self.assertEqual(self.engine.s['revenue'], 1050)

    def test_one_selected_drink_rises_with_sales(self):
        self.engine.settings(dict(DEFAULTS, volatility=0, demand_gain=2))
        for product in self.engine.s['products']:
            self.engine.configure_product(product['id'], dict(
                cost=100, minimum=150, base=400, maximum=800,
                selected=product['id'] == 1,
            ))
        self.engine.start()
        before = self.engine.selected()[0]['price']
        self.engine.manual_sale(1, 19)
        self.engine.tick()
        self.assertGreater(self.engine.selected()[0]['price'], before)

    def test_uncertain_commit_recovery_after_restart(self):
        self.prepare_remote()
        self.remote.fail_after_commit = True
        with self.assertRaises(ConnectionError):
            self.engine.tick()
        self.assertIsNotNone(self.store.get('pending'))
        self.assertEqual(self.engine.snapshot()['status'], 'recovery')
        count = len(self.remote.writes)
        self.engine.tick()
        self.assertEqual(len(self.remote.writes), count)
        self.restart()
        self.assertEqual(len(self.remote.writes), count)
        self.engine.finish()
        self.assertEqual(self.remote.prices, {1: 350, 2: 400})
        self.assertIsNone(self.store.get('pending'))

    def test_start_uncertain_commit_preserves_originals(self):
        self.engine.load_catalog('mysql')
        self.engine.configure_product(1, dict(cost=100, minimum=150, base=500, maximum=800, selected=True))
        self.remote.fail_after_commit = True
        with self.assertRaises(ConnectionError):
            self.engine.start()
        self.assertEqual(self.engine.snapshot()['products'][0]['original'], 350)
        self.engine.finish()
        self.assertEqual(self.remote.prices[1], 350)

    def test_finish_uncertain_commit_can_finish_again(self):
        self.prepare_remote()
        self.remote.fail_after_commit = True
        with self.assertRaises(ConnectionError):
            self.engine.finish()
        self.engine.finish()
        self.assertEqual(self.remote.prices, {1: 350, 2: 400})
        self.assertEqual(self.engine.s['status'], 'closed')

    def test_restart_pauses_without_remote_calls(self):
        self.prepare_remote()
        count = len(self.remote.writes)
        self.restart()
        self.assertEqual(self.engine.s['status'], 'paused')
        self.assertEqual(len(self.remote.writes), count)

    def test_conflict_does_not_overwrite(self):
        self.prepare_remote()
        self.remote.prices[2] = 777
        before = dict(self.remote.prices)
        with self.assertRaises(ValueError):
            self.engine.finish()
        self.assertEqual(self.remote.prices, before)
        self.assertIsNotNone(self.engine.pending())

    def test_wrong_database_blocks_writes(self):
        self.prepare_remote()
        before = dict(self.remote.prices)
        self.remote.key = 'another-database'
        with self.assertRaises(ValueError):
            self.engine.finish()
        self.assertEqual(self.remote.prices, before)

    def test_configuration_locked_during_session(self):
        self.engine.start()
        with self.assertRaises(ValueError):
            self.engine.load_catalog('demo')
        with self.assertRaises(ValueError):
            self.engine.configure_product(1, dict(cost=0, minimum=100, base=200, maximum=300, selected=True))

    def test_restore_even_if_sales_import_fails(self):
        self.prepare_remote()
        self.remote.rows = [dict(id='101', product_id=1, quantity=1, total=400, at='fictive')]
        self.engine.finish()
        self.assertEqual(self.remote.prices, {1: 350, 2: 400})
        self.assertIn('bilan à vérifier', self.engine.s['error'])

    def test_export(self):
        self.engine.start()
        self.engine.manual_sale(1, 2)
        self.engine.finish()
        path = Path(self.engine.export(Path(self.tmp.name) / 'exports'))
        self.assertIn(';700;', (path / 'sales.csv').read_text(encoding='utf-8-sig'))
        self.assertTrue((path / 'history.csv').is_file())
        self.assertIn('original', (path / 'bilan.json').read_text())


if __name__ == '__main__':
    unittest.main()
