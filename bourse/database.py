"""Accès Fouaille direct : catalogue/ventes en lecture, prix en écriture contrôlée."""
import configparser
import hashlib
import os
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlsplit, unquote


def cents(value):
    value = Decimal(str(value).replace(',', '.'))
    if not value.is_finite():
        raise ValueError('Le montant doit être un nombre fini.')
    return int((value * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def read_config(path):
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(path, encoding='utf-8')
    return cfg


class MySQL:
    def __init__(self, config_path):
        self.config_path = config_path

    def settings(self):
        cfg = read_config(self.config_path)
        url = os.environ.get('BOURSE_DATABASE_URL') or cfg.get('mysql', 'url', fallback='')
        p = urlsplit(url)
        if p.scheme != 'mysql' or not p.hostname or not p.username or not p.path.strip('/'):
            raise ValueError('Renseigner une URL mysql:// dans config.ini, section [mysql].')
        if p.query or p.fragment:
            raise ValueError('URL MySQL : encoder les caractères spéciaux du mot de passe ; utiliser ssl_ca pour TLS.')
        args = dict(host=p.hostname, port=p.port or 3306, user=unquote(p.username),
                    password=unquote(p.password or ''), database=unquote(p.path.lstrip('/')),
                    charset='utf8mb4', connect_timeout=5, read_timeout=8, write_timeout=8,
                    autocommit=False)
        ca = cfg.get('mysql', 'ssl_ca', fallback='').strip()
        if ca:
            args.update(ssl_ca=ca, ssl_verify_cert=True, ssl_verify_identity=True)
        return args

    def identity(self):
        s = self.settings()
        return hashlib.sha256(f"{s['host']}:{s['port']}/{s['database']}".encode()).hexdigest()

    def connect(self):
        try:
            import pymysql
        except ImportError as exc:
            raise RuntimeError('Pilote MySQL absent. Lancer Installer_MySQL.command.') from exc
        try:
            return pymysql.connect(**self.settings(), cursorclass=pymysql.cursors.DictCursor)
        except (ValueError, RuntimeError):
            raise
        except Exception as exc:
            # Ne jamais exposer le mot de passe ou l'URL dans les erreurs affichées.
            raise RuntimeError('Connexion MySQL impossible. Vérifier réseau, identifiants et TLS dans config.ini.') from exc

    def catalog(self):
        with self.connect() as db:
            with db.cursor() as c:
                c.execute('SELECT id, name, price FROM products WHERE available=1 ORDER BY name')
                return [dict(id=int(r['id']), name=r['name'], price=cents(r['price'])) for r in c.fetchall()]

    def snapshot(self, ids):
        with self.connect() as db:
            with db.cursor() as c:
                c.execute('SELECT MAX(id) AS n FROM orders')
                baseline = int(c.fetchone()['n'] or 0)
                c.execute('SELECT id, price FROM products WHERE available=1 AND id IN (' +
                          ','.join(['%s'] * len(ids)) + ')', tuple(ids))
                prices = {int(r['id']): cents(r['price']) for r in c.fetchall()}
                if set(prices) != set(ids):
                    raise ValueError('Une boisson sélectionnée a disparu ou est indisponible. Recharger le catalogue.')
                return prices, baseline

    def update_prices(self, changes):
        """Transaction entière, verrouillage et détection de modifications concurrentes.

        Une opération déjà appliquée est acceptée : reprise après coupure entre
        le COMMIT MySQL et le COMMIT SQLite. Aucun autre champ n'est modifié.
        """
        with self.connect() as db:
            try:
                with db.cursor() as c:
                    for product_id, old, new in sorted(changes):
                        c.execute('SELECT price FROM products WHERE id=%s FOR UPDATE', (product_id,))
                        row = c.fetchone()
                        if row is None or cents(row['price']) not in (old, new):
                            raise ValueError(f'Conflit de prix pour le produit {product_id}. Aucune écriture appliquée ; vérifier Fouaille.')
                        if cents(row['price']) != new:
                            c.execute('UPDATE products SET price=%s WHERE id=%s',
                                      (f'{new / 100:.2f}', product_id))
                db.commit()
            except Exception:
                db.rollback()
                raise

    def sales(self, baseline, ids):
        # Relecture depuis le début + dédoublonnage SQLite : les commits arrivés
        # dans un ordre différent des identifiants ne sont pas perdus.
        with self.connect() as db:
            with db.cursor() as c:
                c.execute('SELECT id, product_id, amount, price, date FROM orders '
                          'WHERE id>%s AND product_id IN (' + ','.join(['%s'] * len(ids)) +
                          ') ORDER BY id', (baseline, *ids))
                return [dict(id=str(r['id']), product_id=int(r['product_id']),
                             quantity=int(r['amount']), total=cents(r['price']),
                             at=str(r['date'])) for r in c.fetchall()]
