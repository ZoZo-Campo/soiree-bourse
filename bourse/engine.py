"""Moteur du marché. Aucun accès réseau au démarrage ou en démonstration."""
import copy
import math
import random
import time
import uuid
from datetime import datetime

from .database import cents, read_config

COLORS = ['#60a5fa', '#f472b6', '#34d399', '#fbbf24', '#a78bfa', '#fb923c', '#22d3ee', '#e879f9']
DEFAULTS = dict(threshold=20000, fees=0, interval=10.0, volatility=2.5,
                demand_gain=2.0, crash_drop=30.0, rebound=20.0,
                low_ticks=2, rebound_ticks=5, recovery_ticks=8)
CONFIG_KEYS = dict(threshold='seuil_cagnotte', fees='frais_fixes', interval='intervalle_secondes',
                   volatility='variation_aleatoire_pct', demand_gain='influence_ventes_pct',
                   crash_drop='chute_crash_pct', rebound='rebond_pct', low_ticks='paliers_bas',
                   rebound_ticks='paliers_rebond', recovery_ticks='paliers_retour')


def now():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def validate_settings(values):
    s = dict(values)
    bounds = dict(threshold=(1, 100000000), fees=(0, 100000000), interval=(2, 3600),
                  volatility=(0, 20), demand_gain=(0, 20), crash_drop=(1, 90),
                  rebound=(0, 100), low_ticks=(1, 120), rebound_ticks=(1, 120), recovery_ticks=(1, 120))
    for key, (lo, hi) in bounds.items():
        val = float(s[key])
        if not math.isfinite(val) or not lo <= val <= hi:
            raise ValueError(f'Paramètre {CONFIG_KEYS[key]} : valeur attendue entre {lo} et {hi}.')
        if key in ('threshold', 'fees', 'low_ticks', 'rebound_ticks', 'recovery_ticks'):
            if val != int(val):
                raise ValueError('Les montants en centimes et les nombres de paliers doivent être entiers.')
            s[key] = int(val)
        else:
            s[key] = val
    return s


def configured_settings(path):
    settings = dict(DEFAULTS)
    cfg = read_config(path)
    for key, ini_key in CONFIG_KEYS.items():
        if cfg.has_option('marche', ini_key):
            raw = cfg.get('marche', ini_key)
            settings[key] = cents(raw) if key in ('threshold', 'fees') else float(raw)
    return validate_settings(settings)


def new_product(row, index):
    price = row['price']
    return dict(id=row['id'], name=row['name'], original=price, base=price, price=price,
                previous=price, cost=0, minimum=max(1, round(price * .5)), maximum=max(1, price * 2),
                selected=False, configured=False, color=COLORS[index % len(COLORS)], sold=0, demand=0)


class Engine:
    def __init__(self, store, remote, settings=None, rng=None, clock=time.time):
        self.store, self.remote = store, remote
        self.rng, self.clock = rng or random.Random(), clock
        self.s = store.get('state') or dict(session='', status='ready', mode='demo', phase='normal',
             products=[], settings=settings or dict(DEFAULTS), revenue=0, cost=0, quantity=0,
             last_tick=0, phase_step=0, crash_count=0, error='', baseline=0)
        # Une relance ne modifie jamais la DB automatiquement.
        if self.s['status'] == 'running':
            self.s['status'] = 'paused'
            self.store.commit(self.s, event=(now(), 'Application relancée : marché en pause.'))

    def pending(self):
        return self.store.get('pending')

    def snapshot(self):
        state = copy.deepcopy(self.s)
        pending = self.pending()
        if pending:
            state = copy.deepcopy(pending['state'])
            state['status'] = 'recovery'
            state['error'] = self.s.get('error') or 'Une écriture doit être réconciliée. Reprendre ou restaurer les prix.'
        state['reserve'] = state['revenue'] - state['cost'] - state['settings']['fees']
        state['history'] = self.store.recent_history(state['session']) if state['session'] else []
        state['events'] = self.store.events()
        state['can_crash'] = state['status'] == 'running' and state['phase'] == 'normal' and state['reserve'] >= state['settings']['threshold']
        return state

    def selected(self, state=None):
        return [p for p in (state or self.s)['products'] if p['selected']]

    def require_editable(self):
        if self.pending() or self.s['status'] not in ('ready', 'closed'):
            raise ValueError('Terminer la soirée et restaurer les prix avant de changer le catalogue.')

    def load_catalog(self, mode):
        self.require_editable()
        if mode not in ('demo', 'mysql'):
            raise ValueError('Mode inconnu.')
        if mode == 'demo':
            rows = [dict(id=i+1, name=n, price=p) for i, (n, p) in enumerate([
                ('Bière blonde', 350), ('Bière ambrée', 400), ('Cidre', 300),
                ('Cocktail maison', 550), ('Soda', 200), ('Jus de fruits', 250)])]
        else:
            rows = self.remote.catalog()
        baseline = self.remote.latest_order_id() if mode == 'mysql' else 0
        self.s.update(mode=mode, products=[new_product(r, i) for i, r in enumerate(rows)],
                      status='ready', session='', revenue=0, cost=0, quantity=0, error='', phase='normal',
                      baseline=baseline, baseline_armed=(mode == 'mysql'))
        if mode == 'demo':
            for p in self.s['products']:
                p.update(cost=round(p['base'] * .35), selected=True, configured=True)
        self.store.commit(self.s, event=(now(), f'Catalogue chargé : {len(rows)} boissons ({mode}).'))

    def arm_sales_boundary(self):
        """Start counting at application launch, before the operator configures prices."""
        if self.s['mode'] != 'mysql' or self.s['status'] not in ('ready', 'closed'):
            return
        self.s['baseline'] = self.remote.latest_order_id()
        self.s['baseline_armed'] = True
        self.store.commit(self.s, event=(now(), 'Repère de début enregistré : les prochaines ventes seront comptées.'))

    def configure_product(self, product_id, values):
        self.require_editable()
        p = next(p for p in self.s['products'] if p['id'] == product_id)
        v = {k: int(values[k]) for k in ('cost', 'base', 'minimum', 'maximum')}
        if not 0 <= v['cost'] <= v['minimum'] <= v['base'] <= v['maximum'] <= 99999999 or v['minimum'] < 1:
            raise ValueError('Respecter : 0 ≤ coût ≤ prix minimum ≤ prix initial ≤ maximum (minimum > 0).')
        p.update(v, selected=bool(values['selected']), configured=True, price=v['base'], previous=v['base'])
        self.store.commit(self.s)

    def settings(self, values):
        if self.pending():
            raise ValueError('Réconcilier les prix avant de changer les paramètres.')
        values = validate_settings(values)
        if self.s['status'] in ('running', 'paused') and self.s['phase'] != 'normal':
            raise ValueError('Attendre la fin du cycle crash/rebond pour changer les paramètres.')
        self.s['settings'] = values
        self.store.commit(self.s, event=(now(), 'Paramètres du marché enregistrés.'))

    def check_identity(self, state):
        if self.remote.identity() != state['remote_identity']:
            raise ValueError('La base configurée diffère de celle de la soirée. Rétablir la connexion d’origine pour restaurer les prix.')

    def points(self, state):
        stamp = now()
        return [(state['session'], stamp, p['id'], p['name'], p['price'], state['phase']) for p in self.selected(state)]

    def publish(self, target, message, original_prices=None):
        points = self.points(target)
        if target['mode'] == 'demo':
            self.store.commit(target, points=points, event=(now(), message))
            self.s = target
            return
        self.check_identity(target)
        previous = original_prices or {p['id']: p['price'] for p in self.selected()}
        changes = [(p['id'], previous[p['id']], p['price']) for p in self.selected(target)]
        pending = dict(state=target, changes=changes, points=points, message=message)
        # La sauvegarde inclut TOUS les prix d'origine, avant le premier UPDATE.
        self.store.put('pending', pending)
        try:
            self.remote.update_prices(changes)
            self.store.commit(target, points=points, event=(now(), message), clear_pending=True)
            self.s = target
        except Exception:
            self.s['status'] = 'paused'
            self.s['error'] = 'Écriture non confirmée. Le marché est arrêté ; utiliser Réconcilier ou Fin de soirée.'
            self.store.commit(self.s, event=(now(), self.s['error']))
            raise

    def reconcile(self):
        pending = self.pending()
        if not pending:
            raise ValueError('Aucune écriture en attente.')
        target = pending['state']
        self.check_identity(target)
        self.remote.update_prices(pending['changes'])
        if target['status'] == 'running':
            target['status'] = 'paused'
        target['error'] = ''
        self.store.commit(target, points=pending['points'], event=(now(), 'Écriture réconciliée : ' + pending['message']), clear_pending=True)
        self.s = target

    def start(self):
        self.require_editable()
        products = self.selected()
        if not products or any(not p['configured'] for p in products):
            raise ValueError('Sélectionner des boissons et renseigner leur coût par verre dans Catalogue.')
        target = copy.deepcopy(self.s)
        originals = {p['id']: p['original'] for p in products}
        if target['mode'] == 'mysql':
            target['remote_identity'] = self.remote.identity()
            originals, current_baseline = self.remote.snapshot(list(originals))
            if not target.get('baseline_armed'):
                target['baseline'] = current_baseline
        for p in self.selected(target):
            p.update(original=originals[p['id']], price=p['base'], previous=p['base'], sold=0, demand=0)
        target.update(session=datetime.now().strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:6],
                      status='running', phase='normal', phase_step=0, crash_count=0,
                      revenue=0, cost=0, quantity=0, last_tick=self.clock(), error='', started_at=now(),
                      baseline_armed=False)
        self.publish(target, 'Soirée démarrée. Prix d’origine sauvegardés.', originals)
        # Include sales made since the application/catalogue was opened.
        self.sync_sales()

    def manual_sale(self, product_id, quantity):
        if self.s['mode'] != 'demo':
            raise ValueError('En mode Fouaille, les ventes sont lues depuis orders : aucune double saisie.')
        if self.s['status'] not in ('running', 'paused') or self.pending():
            raise ValueError('Démarrer une soirée avant de saisir une vente.')
        if not isinstance(quantity, int) or not 1 <= quantity <= 1000:
            raise ValueError('Quantité attendue : entier entre 1 et 1000.')
        p = next((p for p in self.selected() if p['id'] == product_id), None)
        if not p:
            raise ValueError('Boisson non sélectionnée.')
        self.ingest([dict(id='local-' + uuid.uuid4().hex, product_id=product_id, quantity=quantity,
                          total=-p['price'] * quantity, at=now())])

    def ingest(self, rows):
        known = self.store.sale_ids(self.s['session'])
        target = copy.deepcopy(self.s)
        products = {p['id']: p for p in self.selected(target)}
        records = []
        for row in rows:
            if row['id'] in known or row['product_id'] not in products:
                continue
            # Ce schéma stocke les achats comme total de ligne négatif.
            if row['total'] >= 0 or row['quantity'] <= 0:
                raise ValueError('Une ligne Fouaille sélectionnée est un remboursement ou a un format non pris en charge. Vérifier les ventes avant de reprendre.')
            p = products[row['product_id']]
            revenue, cost = -row['total'], row['quantity'] * p['cost']
            p['sold'] += row['quantity']
            p['demand'] += row['quantity']
            target['revenue'] += revenue
            target['cost'] += cost
            target['quantity'] += row['quantity']
            records.append((target['session'], row['id'], row['at'], p['id'], p['name'], row['quantity'], revenue, cost))
            known.add(row['id'])
        if records:
            self.store.commit(target, sales=records)
            self.s = target

    def sync_sales(self):
        if self.s['mode'] == 'mysql':
            self.check_identity(self.s)
            self.ingest(self.remote.sales(self.s['baseline'], [p['id'] for p in self.selected()]))

    def pause(self):
        if self.pending():
            raise ValueError('Réconcilier l’écriture en attente.')
        if self.s['status'] == 'running':
            self.s.update(status='paused', error='')
        elif self.s['status'] == 'paused':
            self.sync_sales()
            self.s.update(status='running', last_tick=self.clock(), error='')
        else:
            raise ValueError('Aucune soirée à mettre en pause ou reprendre.')
        self.store.commit(self.s, event=(now(), 'Marché ' + ('en pause.' if self.s['status'] == 'paused' else 'repris.')))

    @staticmethod
    def bounded(p, price):
        return max(p['minimum'], min(p['maximum'], int(round(price))))

    def crash(self):
        if self.pending() or self.s['status'] != 'running' or self.s['phase'] != 'normal':
            raise ValueError('Le crash est disponible uniquement pendant le marché normal, sans écriture en attente.')
        self.sync_sales()
        if self.snapshot()['reserve'] < self.s['settings']['threshold']:
            raise ValueError('La cagnotte de sécurité est insuffisante.')
        target = copy.deepcopy(self.s)
        target.update(phase='crash', phase_step=0, last_tick=self.clock(), crash_count=target['crash_count'] + 1)
        for p in self.selected(target):
            p.update(anchor=p['price'], previous=p['price'])
            p['price'] = self.bounded(p, p['anchor'] * (1 - target['settings']['crash_drop'] / 100))
            p['bottom'] = p['price']
        self.publish(target, 'Crash déclenché manuellement par l’organisateur.')

    def tick(self):
        if self.pending() or self.s['status'] != 'running':
            return
        self.sync_sales()
        target = copy.deepcopy(self.s)
        cfg = target['settings']
        products = self.selected(target)
        target['phase_step'] += 1
        phase, step = target['phase'], target['phase_step']
        total_demand = sum(p['demand'] for p in products)
        for p in products:
            p['previous'] = p['price']
            if phase == 'normal':
                # log1p keeps large batches controlled while ensuring that a
                # sold drink rises even when it is the only selected product.
                pressure = math.log1p(p['demand']) if total_demand else 0
                noise = self.rng.uniform(-cfg['volatility'], cfg['volatility']) / 100
                drift = .001 if target['revenue'] - target['cost'] - cfg['fees'] < cfg['threshold'] else 0
                reversion = .04 * (p['base'] - p['price'])
                value = p['price'] * (1 + noise + pressure * cfg['demand_gain'] / 100 + drift) + reversion
            elif phase == 'crash':
                value = p['bottom']
            elif phase == 'rebound':
                peak = self.bounded(p, p['anchor'] * (1 + cfg['rebound'] / 100))
                value = p['bottom'] + (peak - p['bottom']) * step / cfg['rebound_ticks']
            else:
                peak = self.bounded(p, p['anchor'] * (1 + cfg['rebound'] / 100))
                value = peak + (p['anchor'] - peak) * step / cfg['recovery_ticks']
            p['price'] = self.bounded(p, value)
            p['demand'] = 0
        transitions = dict(crash=(cfg['low_ticks'], 'rebound'), rebound=(cfg['rebound_ticks'], 'recovery'), recovery=(cfg['recovery_ticks'], 'normal'))
        if phase in transitions and step >= transitions[phase][0]:
            target.update(phase=transitions[phase][1], phase_step=0)
        target['last_tick'] = self.clock()
        self.publish(target, 'Cours actualisés · ' + target['phase'])

    def due(self):
        return self.s['status'] == 'running' and not self.pending() and self.clock() - self.s['last_tick'] >= self.s['settings']['interval']

    def failure(self, message):
        if self.s['status'] == 'running':
            self.s['status'] = 'paused'
        self.s['error'] = message
        self.store.commit(self.s, event=(now(), message))

    def finish(self):
        if self.pending():
            self.reconcile()
            if self.s['status'] == 'closed':
                return
        if self.s['status'] not in ('running', 'paused'):
            raise ValueError('Aucune soirée en cours à terminer.')
        warning = ''
        try:
            self.sync_sales()
        except Exception:
            # La restauration reste prioritaire même si orders est illisible.
            warning = 'Prix restaurés, mais le dernier import des ventes a échoué : bilan à vérifier.'
        target = copy.deepcopy(self.s)
        for p in self.selected(target):
            p.update(previous=p['price'], price=p['original'])
        target.update(status='closed', phase='closed', error=warning, ended_at=now())
        self.publish(target, warning or 'Fin de soirée : tous les prix sélectionnés ont été restaurés.')

    def export(self, folder):
        state = self.snapshot()
        if not state['session']:
            raise ValueError('Aucune soirée à exporter.')
        for key in ('history', 'events', 'can_crash'):
            state.pop(key, None)
        return self.store.export(folder, state)
