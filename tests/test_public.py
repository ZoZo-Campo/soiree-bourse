"""Vérifie la séparation des informations spectateurs/serveurs, sans base ni réseau."""
import copy
import json
import unittest
from bourse.public import public_snapshot


class PublicScreenTests(unittest.TestCase):
    def sample(self):
        return dict(status='running', revenue=123456, reserve=20000, cost=7777,
                    settings={'threshold': 20000}, error='SECRET_TECHNIQUE', crash_count=3,
                    products=[dict(id=1, name='Boisson visible', price=350, previous=300,
                                   color='#60a5fa', selected=True, cost=99, sold=777,
                                   original=123, minimum=99, maximum=999),
                              dict(id=2, name='BOISSON_NON_SELECTIONNEE', price=400, previous=400,
                                   color='#f472b6', selected=False, cost=100)],
                    history=[dict(at='2026-09-09T20:00:00+02:00', product_id=1,
                                  price=300, session='IDENTIFIANT_PRIVE', phase='normal'),
                             dict(at='2026-09-09T20:00:00+02:00', product_id=2,
                                  price=400, session='IDENTIFIANT_PRIVE', phase='normal')])

    def test_only_public_fields_and_selected_drinks_are_transmitted(self):
        public = public_snapshot(self.sample())
        encoded = json.dumps(public)
        for private in ['SECRET_TECHNIQUE', 'IDENTIFIANT_PRIVE', 'BOISSON_NON_SELECTIONNEE',
                        'revenue', 'reserve', 'cost', 'sold', 'settings', 'original', 'minimum', 'phase']:
            self.assertNotIn(private, encoded)
        self.assertEqual(public['products'][0]['price'], 350)
        self.assertEqual(public['products'][0]['previous'], 300)
        self.assertEqual(len(public['products']), 1)
        self.assertEqual(len(public['history']), 1)

    def test_uncertain_prices_are_hidden_until_confirmed(self):
        state = self.sample()
        state['status'] = 'recovery'
        public = public_snapshot(state)
        self.assertEqual(public['products'], [])
        self.assertEqual(public['history'], [])
        self.assertNotIn('SECRET_TECHNIQUE', json.dumps(public))
        self.assertIn('indisponibles', public['message'])

    def test_ready_state_does_not_advertise_unapplied_prices(self):
        state = self.sample()
        state['status'] = 'ready'
        self.assertEqual(public_snapshot(state)['products'], [])

    def test_public_state_is_independent_and_updates_on_next_snapshot(self):
        state = self.sample()
        before = copy.deepcopy(state)
        first = public_snapshot(state)
        first['products'][0]['price'] = 1
        self.assertEqual(state, before)
        state['products'][0].update(price=420, previous=350)
        next_state = public_snapshot(state)
        self.assertEqual(next_state['products'][0]['price'], 420)
        self.assertEqual(next_state['products'][0]['previous'], 350)


if __name__ == '__main__':
    unittest.main()
