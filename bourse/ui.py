"""Interface native Tkinter. Réseau et disque servis par un seul travailleur."""
import copy
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox

from .database import MySQL, cents
from .engine import Engine, configured_settings
from .storage import Store
from .charts import draw_price_chart
from .public import PublicDisplay, public_snapshot

BG = '#0b1220'
PANEL = '#111e31'
TEXT = '#e7eefb'
MUTED = '#97aac4'
GREEN = '#34d399'
RED = '#fb7185'
PHASES = dict(normal='Marché ouvert', crash='Crash · prix bas', rebound='Rebond', recovery='Retour progressif', closed='Soirée terminée')
STATUS = dict(ready='PRÊT', running='EN DIRECT', paused='EN PAUSE', closed='TERMINÉ', recovery='À RÉCONCILIER')


def money(value):
    return f'{value / 100:,.2f} €'.replace(',', ' ').replace('.', ',')


class Worker(threading.Thread):
    def __init__(self, root_path, inbox, outbox):
        super().__init__(daemon=True)
        self.root_path, self.inbox, self.outbox = root_path, inbox, outbox

    def run(self):
        store = None
        try:
            store = Store(self.root_path / 'data' / 'soiree.sqlite3')
            engine = Engine(store, MySQL(self.root_path / 'config.ini'), configured_settings(self.root_path / 'config.ini'))
            if not engine.s['products'] and not engine.pending():
                engine.load_catalog('demo')
            elif not engine.pending():
                engine.arm_sales_boundary()
            self.outbox.put(('state', engine.snapshot(), None))
            while True:
                try:
                    name, args = self.inbox.get(timeout=.25)
                except queue.Empty:
                    if not engine.due():
                        continue
                    name, args = 'tick', ()
                try:
                    if name == 'quit':
                        if engine.s['status'] == 'running':
                            engine.pause()
                        self.outbox.put(('quit', None, None))
                        break
                    result = getattr(engine, name)(*args)
                    self.outbox.put(('state', engine.snapshot(), (name, result)))
                except Exception as exc:
                    message = str(exc) or type(exc).__name__
                    engine.failure(message)
                    self.outbox.put(('error', engine.snapshot(), message))
        except Exception as exc:
            self.outbox.put(('fatal', None, str(exc)))
        finally:
            if store:
                store.close()


class App:
    def __init__(self, root, root_path):
        self.root, self.path = root, Path(root_path)
        self.state, self.busy, self.quitting = None, False, False
        self.public_display = None
        self.inbox, self.outbox = queue.Queue(), queue.Queue()
        root.title('Soirée Bourse · Espace serveurs')
        width = min(1400, root.winfo_screenwidth() - 60)
        height = min(900, root.winfo_screenheight() - 100)
        root.geometry(f'{width}x{height}+30+40')
        root.minsize(980, 680)
        root.configure(bg=BG)
        self.style()
        self.build()
        root.protocol('WM_DELETE_WINDOW', self.close)
        Worker(self.path, self.inbox, self.outbox).start()
        root.after(100, self.poll)

    def style(self):
        s = ttk.Style()
        s.theme_use('clam')
        s.configure('.', font=('Helvetica', 12), background=BG, foreground=TEXT)
        s.configure('TFrame', background=BG)
        s.configure('TLabel', background=BG, foreground=TEXT)
        s.configure('Muted.TLabel', foreground=MUTED)
        s.configure('TButton', padding=(12, 9), background='#243751', foreground=TEXT, borderwidth=0)
        s.map('TButton', background=[('active', '#345477'), ('disabled', '#152135')], foreground=[('disabled', '#64748b')])
        s.configure('Accent.TButton', background='#126d5d', foreground='#ffffff')
        s.map('Accent.TButton', background=[('active', '#168874'), ('disabled', '#152135')])
        s.configure('Danger.TButton', background='#a92e49', foreground='#ffffff')
        s.map('Danger.TButton', background=[('active', '#cb3859'), ('disabled', '#152135')])
        s.configure('Treeview', background=PANEL, fieldbackground=PANEL, foreground=TEXT, rowheight=36, borderwidth=0)
        s.configure('Treeview.Heading', background='#1c2d45', foreground=MUTED, padding=8)
        s.map('Treeview', background=[('selected', '#285477')], foreground=[('selected', '#ffffff')])
        s.configure('TNotebook', background=BG, borderwidth=0)
        s.configure('TNotebook.Tab', background=PANEL, foreground=MUTED, padding=(20, 12))
        s.map('TNotebook.Tab', background=[('selected', '#243751')], foreground=[('selected', TEXT)])
        s.configure('TEntry', fieldbackground='#1c2d45', foreground=TEXT, insertcolor=TEXT, padding=7)
        s.configure('TCheckbutton', background=BG, foreground=TEXT)
        s.map('TCheckbutton', background=[('active', BG)])
        s.configure('TCombobox', fieldbackground='#1c2d45', foreground=TEXT, padding=6)
        s.map('TCombobox', fieldbackground=[('readonly', '#1c2d45')], foreground=[('readonly', TEXT)])
        s.configure('Horizontal.TProgressbar', background=GREEN, troughcolor='#243751', borderwidth=0)

    def build(self):
        outer = ttk.Frame(self.root, padding=22)
        outer.pack(fill='both', expand=True)
        head = ttk.Frame(outer)
        head.pack(fill='x')
        ttk.Label(head, text='SOIRÉE BOURSE', font=('Helvetica', 25, 'bold')).pack(side='left')
        self.badge = ttk.Label(head, text='Chargement…', foreground=GREEN)
        self.badge.pack(side='right')
        tools = ttk.Frame(outer)
        tools.pack(fill='x', pady=(5, 12))
        ttk.Label(tools, text='Espace serveurs · ventes, cagnotte et commandes', style='Muted.TLabel').pack(side='left')
        ttk.Button(tools, text='Plein écran public', command=self.fullscreen_public).pack(side='right')
        ttk.Button(tools, text='Ouvrir l’écran public', command=self.open_public, style='Accent.TButton').pack(side='right', padx=(8, 8))
        cards = ttk.Frame(outer)
        cards.pack(fill='x')
        self.metrics = {}
        for i, (key, label) in enumerate([('revenue', 'RECETTES'), ('margin', 'MARGE BRUTE'), ('reserve', 'CAGNOTTE NETTE'), ('quantity', 'VERRES VENDUS')]):
            card = tk.Frame(cards, bg=PANEL, padx=18, pady=12)
            card.grid(row=0, column=i, sticky='ew', padx=(0 if i == 0 else 10, 0))
            cards.columnconfigure(i, weight=1)
            tk.Label(card, text=label, bg=PANEL, fg=MUTED, font=('Helvetica', 10, 'bold')).pack(anchor='w')
            v = tk.Label(card, text='—', bg=PANEL, fg=GREEN if key == 'reserve' else TEXT, font=('Helvetica', 24, 'bold'))
            v.pack(anchor='w', pady=(6, 0))
            self.metrics[key] = v
        bar = ttk.Frame(outer)
        bar.pack(fill='x', pady=(12, 4))
        self.reserve_text = ttk.Label(bar, text='Seuil de sécurité : 200 €', style='Muted.TLabel')
        self.reserve_text.pack(side='left')
        self.progress = ttk.Progressbar(bar, length=260, mode='determinate')
        self.progress.pack(side='right')
        controls = ttk.Frame(outer)
        controls.pack(fill='x', pady=12)
        self.start_button = ttk.Button(controls, text='Démarrer la soirée', command=self.start, style='Accent.TButton')
        self.start_button.pack(side='left', padx=(0, 8))
        self.pause_button = ttk.Button(controls, text='Pause', command=lambda: self.call('pause'))
        self.pause_button.pack(side='left', padx=(0, 8))
        self.crash_button = ttk.Button(controls, text='Déclencher un crash', command=self.crash, style='Danger.TButton')
        self.crash_button.pack(side='left', padx=(0, 8))
        self.finish_button = ttk.Button(controls, text='Fin de soirée : restaurer les prix', command=self.finish)
        self.finish_button.pack(side='right')
        self.notice = ttk.Label(outer, text='', style='Muted.TLabel', wraplength=1250)
        self.notice.pack(fill='x', pady=(0, 10))
        self.tabs = ttk.Notebook(outer)
        self.tabs.pack(fill='both', expand=True)
        self.market_tab, self.sale_tab, self.catalog_tab, self.settings_tab, self.control_tab, self.log_tab = [ttk.Frame(self.tabs, padding=14) for _ in range(6)]
        for tab, title in zip((self.market_tab, self.sale_tab, self.catalog_tab, self.settings_tab, self.control_tab, self.log_tab), ('Cours en direct', 'Ventes', 'Catalogue', 'Réglages', 'Sécurité prix', 'Journal & exports')):
            self.tabs.add(tab, text=title)
        self.build_market()
        self.build_sales()
        self.build_catalog()
        self.build_settings()
        self.build_price_control()
        self.build_log()
        ttk.Label(outer, text='Sauvegarde locale automatique • Le prix d’une vente reste celui réellement payé.', style='Muted.TLabel').pack(anchor='w', pady=(10, 0))

    def table(self, parent, columns, height=7, use_pack=True):
        box = ttk.Frame(parent)
        if use_pack:
            box.pack(fill='both', expand=True)
        tree = ttk.Treeview(box, columns=[c[0] for c in columns], show='headings', height=height, selectmode='browse')
        for key, text, width in columns:
            tree.heading(key, text=text)
            tree.column(key, width=width, anchor='w' if key == 'name' else 'center', minwidth=55)
        scroll = ttk.Scrollbar(box, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        return tree

    def build_market(self):
        self.market_tab.columnconfigure(0, weight=1)
        self.market_tab.rowconfigure(2, weight=3, minsize=100)
        self.market_tab.rowconfigure(3, weight=2, minsize=125)
        self.phase_label = ttk.Label(self.market_tab, text='Choisir les boissons puis démarrer', font=('Helvetica', 16, 'bold'))
        self.phase_label.grid(row=0, column=0, sticky='w', pady=(0, 6))
        self.legend = ttk.Frame(self.market_tab)
        self.legend.grid(row=1, column=0, sticky='ew')
        self.canvas = tk.Canvas(self.market_tab, bg=PANEL, highlightthickness=0, height=160)
        self.canvas.grid(row=2, column=0, sticky='nsew', pady=8)
        self.canvas.bind('<Configure>', lambda _: self.draw_chart())
        self.market_tree = self.table(self.market_tab, [('name', 'Boisson', 230), ('price', 'Prix actuel', 120), ('change', 'Dernier mouvement', 150), ('base', 'Depuis le prix initial', 170), ('margin', 'Marge / verre', 140), ('sold', 'Verres vendus', 120)], height=4, use_pack=False)
        self.market_tree.master.grid(row=3, column=0, sticky='nsew')

    def build_sales(self):
        self.sales_help = ttk.Label(self.sale_tab, text='', wraplength=1150, style='Muted.TLabel')
        self.sales_help.pack(anchor='w', pady=(0, 12))
        self.sale_tree = self.table(self.sale_tab, [('name', 'Boisson', 300), ('price', 'Prix du verre', 150), ('margin', 'Marge du verre', 150), ('sold', 'Verres vendus', 140)])
        row = ttk.Frame(self.sale_tab)
        row.pack(fill='x', pady=16)
        ttk.Label(row, text='Quantité').pack(side='left', padx=(0, 8))
        self.quantity = tk.StringVar(value='1')
        ttk.Entry(row, textvariable=self.quantity, width=7).pack(side='left', padx=(0, 12))
        self.sale_button = ttk.Button(row, text='Enregistrer la vente locale', command=self.sale, style='Accent.TButton')
        self.sale_button.pack(side='left')
        self.sync_button = ttk.Button(row, text='Actualiser les ventes Fouaille', command=lambda: self.call('sync_sales'))
        self.sync_button.pack(side='right')

    def build_catalog(self):
        row = ttk.Frame(self.catalog_tab)
        row.pack(fill='x', pady=(0, 10))
        self.mode = tk.StringVar(value='Démonstration / caisse locale')
        ttk.Combobox(row, textvariable=self.mode, values=['Démonstration / caisse locale', 'Fouaille MySQL · prix partagés'], state='readonly', width=34).pack(side='left', padx=(0, 10))
        self.load_button = ttk.Button(row, text='Charger le catalogue', command=self.load_catalog)
        self.load_button.pack(side='left')
        self.edit_button = ttk.Button(row, text='Configurer la boisson sélectionnée', command=self.edit_product)
        self.edit_button.pack(side='right')
        ttk.Label(self.catalog_tab, text='Double-cliquer une boisson pour la sélectionner et régler son coût, son prix initial et ses limites.\nLes coûts sont à renseigner : le catalogue Fouaille ne fournit pas le coût par verre.', style='Muted.TLabel').pack(anchor='w', pady=(0, 12))
        self.catalog_tree = self.table(self.catalog_tab, [('selected', 'Vendue ce soir', 110), ('name', 'Boisson', 240), ('original', 'Prix catalogue', 110), ('cost', 'Coût / verre', 110), ('base', 'Prix initial', 110), ('minimum', 'Minimum', 100), ('maximum', 'Maximum', 100)])
        self.catalog_tree.bind('<Double-1>', lambda _: self.edit_product())

    def build_settings(self):
        ttk.Label(self.settings_tab, text='La cagnotte = recettes − coût des verres vendus − frais fixes.', font=('Helvetica', 14, 'bold')).pack(anchor='w', pady=(0, 8))
        ttk.Label(self.settings_tab, text='Un mouvement de cours ne crée pas de bénéfice. Les prix minimums restent au moins égaux au coût par verre.', style='Muted.TLabel').pack(anchor='w', pady=(0, 12))
        grid = ttk.Frame(self.settings_tab)
        grid.pack(anchor='w')
        self.setting_vars = {}
        fields = [('threshold', 'Seuil de sécurité (€)'), ('fees', 'Frais fixes (€)'), ('interval', 'Actualisation (secondes)'), ('volatility', 'Aléatoire maximum (%)'), ('demand_gain', 'Influence des ventes (%)'), ('crash_drop', 'Chute lors du crash (%)'), ('rebound', 'Rebond au-dessus du prix avant crash (%)'), ('low_ticks', 'Paliers à prix bas'), ('rebound_ticks', 'Paliers de remontée'), ('recovery_ticks', 'Paliers de retour')]
        for i, (key, label) in enumerate(fields):
            col, row = (i // 5) * 2, i % 5
            ttk.Label(grid, text=label).grid(row=row, column=col, sticky='w', padx=(0 if col == 0 else 35, 14), pady=7)
            var = tk.StringVar()
            ttk.Entry(grid, textvariable=var, width=10).grid(row=row, column=col + 1, pady=7)
            self.setting_vars[key] = var
        ttk.Button(self.settings_tab, text='Enregistrer les réglages', command=self.save_settings, style='Accent.TButton').pack(anchor='w', pady=18)
        ttk.Label(self.settings_tab, text='Les réglages enregistrés sont conservés entre les lancements. config.ini définit les valeurs du premier lancement.\nLa pause fige les cours. En mode Fouaille, utiliser Actualiser les ventes pour importer les ventes pendant la pause.', style='Muted.TLabel', wraplength=1120).pack(anchor='w')

    def build_price_control(self):
        ttk.Label(self.control_tab, text='Sauvegarde locale et commandes de secours', font=('Helvetica', 14, 'bold')).pack(anchor='w', pady=(0, 6))
        ttk.Label(self.control_tab, text='Le prix d’origine est lu dans Fouaille au démarrage et conservé dans data/soiree.sqlite3. Les commandes ci-dessous modifient uniquement products.price.', style='Muted.TLabel', wraplength=1120).pack(anchor='w', pady=(0, 12))
        self.control_tree = self.table(self.control_tab, [('name', 'Produit', 300), ('original', 'Prix sauvegardé', 150), ('current', 'Prix actuel', 140), ('minimum', 'Minimum', 120), ('maximum', 'Maximum', 120)], height=6)
        row = ttk.Frame(self.control_tab)
        row.pack(fill='x', pady=14)
        ttk.Label(row, text='Pas manuel (%)').pack(side='left', padx=(0, 8))
        self.manual_step = tk.StringVar(value='10')
        ttk.Entry(row, textvariable=self.manual_step, width=7).pack(side='left', padx=(0, 12))
        self.down_button = ttk.Button(row, text='↓ Forcer la baisse', command=lambda: self.force_price(-1))
        self.down_button.pack(side='left', padx=(0, 8))
        self.up_button = ttk.Button(row, text='↑ Forcer la hausse', command=lambda: self.force_price(1), style='Accent.TButton')
        self.up_button.pack(side='left', padx=(0, 8))
        self.restore_one_button = ttk.Button(row, text='Restaurer ce produit', command=self.restore_one)
        self.restore_one_button.pack(side='left')
        self.restore_all_button = ttk.Button(row, text='Restaurer tous les prix et terminer', command=self.finish, style='Danger.TButton')
        self.restore_all_button.pack(side='right')

    def build_log(self):
        row = ttk.Frame(self.log_tab)
        row.pack(fill='x', pady=(0, 10))
        ttk.Button(row, text='Exporter ventes, courbes et bilan', command=lambda: self.call('export', str(self.path / 'exports'))).pack(side='left')
        self.reconcile_button = ttk.Button(row, text='Réconcilier l’écriture en attente', command=lambda: self.call('reconcile'))
        self.reconcile_button.pack(side='right')
        ttk.Label(self.log_tab, text='En cas de coupure : les prix d’origine restent sauvegardés. Réconcilier confirme l’écriture interrompue, puis laisse le marché en pause.', style='Muted.TLabel', wraplength=1150).pack(anchor='w', pady=(0, 10))
        self.log_text = tk.Text(self.log_tab, bg=PANEL, fg=TEXT, font=('Menlo', 11), wrap='word', relief='flat', padx=12, pady=12)
        self.log_text.pack(fill='both', expand=True)
        self.log_text.configure(state='disabled')

    def call(self, name, *args):
        if self.busy:
            return
        self.busy = True
        self.notice.configure(text='Opération en cours…', foreground=MUTED)
        self.buttons()
        self.inbox.put((name, args))

    def poll(self):
        try:
            while True:
                kind, state, result = self.outbox.get_nowait()
                self.busy = False
                if kind == 'quit':
                    self.root.destroy()
                    return
                if kind == 'fatal':
                    messagebox.showerror('Démarrage impossible', result, parent=self.root)
                    self.root.destroy()
                    return
                if state:
                    self.render(state)
                if kind == 'error':
                    self.quitting = False
                    messagebox.showerror('Opération arrêtée', result, parent=self.root)
                elif result and result[0] == 'export':
                    messagebox.showinfo('Export terminé', 'Fichiers enregistrés dans :\n' + result[1] + '\n\nLes montants des CSV sont en centimes.', parent=self.root)
                elif result and result[0] == 'finish' and self.quitting:
                    self.call('quit')
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def buttons(self):
        s = self.state
        if not s:
            return
        status = s['status']
        editable = status in ('ready', 'closed')
        active = status in ('running', 'paused')
        states = [(self.start_button, editable), (self.pause_button, active), (self.crash_button, s['can_crash']),
                  (self.finish_button, active or status == 'recovery'), (self.load_button, editable),
                  (self.edit_button, editable), (self.sale_button, active and s['mode'] == 'demo'),
                  (self.sync_button, active and s['mode'] == 'mysql'), (self.reconcile_button, status == 'recovery'),
                  (self.down_button, active), (self.up_button, active), (self.restore_one_button, active),
                  (self.restore_all_button, active or status == 'recovery')]
        for button, enabled in states:
            button.configure(state='normal' if enabled and not self.busy else 'disabled')
        self.pause_button.configure(text='Reprendre' if status == 'paused' else 'Pause')

    def render(self, state):
        first = self.state is None
        self.state = state
        s = state
        self.badge.configure(text=('FOUAILLE MYSQL' if s['mode'] == 'mysql' else 'LOCAL · DONNÉES FICTIVES') + '  /  ' + STATUS[s['status']])
        values = dict(revenue=money(s['revenue']), margin=money(s['revenue'] - s['cost']), reserve=money(s['reserve']), quantity=str(s['quantity']))
        for key, value in values.items():
            self.metrics[key].configure(text=value)
        self.reserve_text.configure(text=f"Cagnotte {money(s['reserve'])} / {money(s['settings']['threshold'])} · Frais fixes : {money(s['settings']['fees'])}")
        self.progress['value'] = max(0, min(100, s['reserve'] / s['settings']['threshold'] * 100))
        if s['error']:
            notice = s['error']
        elif s['status'] == 'ready':
            notice = 'Configurer le catalogue et les coûts, puis démarrer la soirée.'
        elif s['status'] == 'closed':
            notice = 'Soirée terminée · prix d’origine restaurés. Le bilan peut être exporté.'
        elif s['status'] == 'paused':
            notice = 'Cours en pause. Les derniers prix restent appliqués. Reprendre ou terminer pour restaurer les tarifs.'
        elif s['can_crash']:
            notice = 'Seuil atteint : le crash est disponible et attend votre confirmation.'
        else:
            notice = 'Le crash reste manuel. Les fluctuations seules ne remplissent pas la cagnotte.'
        self.notice.configure(text=notice, foreground=RED if s['error'] else MUTED)
        self.phase_label.configure(text=PHASES[s['phase']] + f"  ·  {s['crash_count']} crash(s)" + (' · cours non confirmés' if s['status'] == 'recovery' else ''))
        self.sales_help.configure(text=('Ventes locales sur les boissons fictives. Sélectionner une boisson, saisir la quantité et enregistrer. Aucun débit Fouaille.' if s['mode'] == 'demo' else 'Les ventes sont importées automatiquement depuis Fouaille à chaque actualisation du marché. Recettes calculées au prix réellement payé ; aucune double saisie ici.'))
        chosen = [p for p in s['products'] if p['selected']]
        self.fill_table(self.market_tree, chosen, lambda p: (p['name'], money(p['price']), f"{(p['price'] / p['previous'] - 1) * 100:+.1f} %" if p['previous'] else '—', f"{(p['price'] / p['base'] - 1) * 100:+.1f} %" if p['base'] else '—', money(p['price'] - p['cost']), p['sold']))
        self.fill_table(self.sale_tree, chosen, lambda p: (p['name'], money(p['price']), money(p['price'] - p['cost']), p['sold']))
        self.fill_table(self.catalog_tree, s['products'], lambda p: ('Oui' if p['selected'] else '—', p['name'], money(p['original']), money(p['cost']) if p['configured'] else 'À renseigner', money(p['base']), money(p['minimum']), money(p['maximum'])))
        self.fill_table(self.control_tree, chosen, lambda p: (p['name'], money(p['original']), money(p['price']), money(p['minimum']), money(p['maximum'])))
        if first:
            self.mode.set('Fouaille MySQL · prix partagés' if s['mode'] == 'mysql' else 'Démonstration / caisse locale')
            for key, var in self.setting_vars.items():
                var.set(str(s['settings'][key] / 100 if key in ('threshold', 'fees') else s['settings'][key]))
        self.log_text.configure(state='normal')
        self.log_text.delete('1.0', 'end')
        self.log_text.insert('end', '\n\n'.join(f"{e['at']}  {e['message']}" for e in s['events']))
        self.log_text.configure(state='disabled')
        self.buttons()
        self.draw_chart()
        if first:
            self.open_public()
            if s.get('interrupted'):
                self.root.after(300, self.interrupted_session)
        elif self.public_display and not self.public_display.closed:
            self.public_display.render(public_snapshot(state))

    @staticmethod
    def fill_table(tree, products, values):
        selection = tree.selection()
        y = tree.yview()
        tree.delete(*tree.get_children())
        for p in products:
            tag = str(p['id'])
            tree.tag_configure(tag, foreground=p['color'])
            tree.insert('', 'end', iid=tag, values=values(p), tags=(tag,))
        for item in selection:
            if tree.exists(item):
                tree.selection_set(item)
        if y:
            tree.yview_moveto(y[0])

    def draw_chart(self):
        if not self.state:
            return
        canvas = self.canvas
        canvas.delete('all')
        for child in self.legend.winfo_children():
            child.destroy()
        products = [p for p in self.state['products'] if p['selected']]
        for i, p in enumerate(products):
            ttk.Label(self.legend, text='● ' + p['name'], foreground=p['color'], font=('Helvetica', 10)).grid(row=i // 6, column=i % 6, sticky='w', padx=(0, 16))
        draw_price_chart(canvas, products, self.state['history'],
                         empty_text='Les courbes apparaîtront au démarrage de la soirée.\nUne couleur par boisson, prix en euros.')

    def open_public(self):
        if not self.public_display or self.public_display.closed:
            self.public_display = PublicDisplay(self.root)
        else:
            self.public_display.window.deiconify()
            self.public_display.window.lift()
        if self.state:
            self.public_display.render(public_snapshot(self.state))

    def fullscreen_public(self):
        self.open_public()
        self.public_display.fullscreen()

    def load_catalog(self):
        mode = 'mysql' if self.mode.get().startswith('Fouaille') else 'demo'
        if mode == 'mysql' and not messagebox.askokcancel('Lecture du catalogue Fouaille', 'Cette action se connecte à la base configurée dans config.ini pour lire les boissons. Aucun prix n’est modifié avant le démarrage de la soirée.', parent=self.root):
            return
        self.call('load_catalog', mode)

    def edit_product(self):
        if self.busy or not self.state or self.state['status'] not in ('ready', 'closed'):
            return
        sel = self.catalog_tree.selection()
        if not sel:
            messagebox.showinfo('Catalogue', 'Sélectionner une boisson dans le tableau.', parent=self.root)
            return
        p = next(p for p in self.state['products'] if p['id'] == int(sel[0]))
        win = tk.Toplevel(self.root)
        win.title('Configurer · ' + p['name'])
        win.configure(bg=BG)
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()
        box = ttk.Frame(win, padding=24)
        box.pack(fill='both', expand=True)
        ttk.Label(box, text=p['name'], font=('Helvetica', 18, 'bold')).grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 14))
        selected = tk.BooleanVar(value=p['selected'])
        ttk.Checkbutton(box, text='Vendre cette boisson ce soir', variable=selected).grid(row=1, column=0, columnspan=2, sticky='w', pady=8)
        variables = {}
        for i, (key, label) in enumerate([('cost', 'Coût d’un verre (€)'), ('base', 'Prix initial (€)'), ('minimum', 'Prix minimum (€)'), ('maximum', 'Prix maximum (€)')], 2):
            ttk.Label(box, text=label).grid(row=i, column=0, sticky='w', padx=(0, 20), pady=7)
            var = tk.StringVar(value=f"{p[key] / 100:.2f}")
            ttk.Entry(box, textvariable=var, width=12).grid(row=i, column=1, pady=7)
            variables[key] = var
        margin = ttk.Label(box, text='', foreground=GREEN)
        margin.grid(row=6, column=0, columnspan=2, sticky='w', pady=12)
        def update_margin(*_):
            try:
                cost, base = cents(variables['cost'].get()), cents(variables['base'].get())
                margin.configure(text=f'Marge initiale : {money(base-cost)} / verre · {(base-cost)/base*100:.1f} % du prix de vente' if base else 'Prix initial à renseigner')
            except Exception:
                margin.configure(text='Montants à renseigner')
        for var in variables.values():
            var.trace_add('write', update_margin)
        update_margin()
        def save():
            try:
                values = {key: cents(var.get()) for key, var in variables.items()}
                values['selected'] = selected.get()
                if not 0 <= values['cost'] <= values['minimum'] <= values['base'] <= values['maximum'] or values['minimum'] < 1:
                    raise ValueError('Respecter : coût ≤ minimum ≤ prix initial ≤ maximum, avec minimum > 0.')
            except Exception as exc:
                messagebox.showerror('Valeurs invalides', str(exc), parent=win)
                return
            win.destroy()
            self.call('configure_product', p['id'], values)
        ttk.Button(box, text='Enregistrer', command=save, style='Accent.TButton').grid(row=7, column=0, columnspan=2, sticky='ew')

    def save_settings(self):
        try:
            values = {key: cents(var.get()) if key in ('threshold', 'fees') else float(var.get().replace(',', '.')) for key, var in self.setting_vars.items()}
            from .engine import validate_settings
            validate_settings(values)
        except Exception as exc:
            messagebox.showerror('Réglages invalides', str(exc), parent=self.root)
            return
        self.call('settings', values)

    def selected_control_product(self):
        selected = self.control_tree.selection()
        if not selected:
            messagebox.showinfo('Sécurité prix', 'Sélectionner un produit dans le tableau.', parent=self.root)
            return None
        return int(selected[0])

    def force_price(self, direction):
        product_id = self.selected_control_product()
        if product_id is None:
            return
        try:
            percent = float(self.manual_step.get().replace(',', '.'))
            if not 1 <= percent <= 100:
                raise ValueError()
        except ValueError:
            messagebox.showerror('Variation manuelle', 'Saisir un pourcentage entre 1 et 100.', parent=self.root)
            return
        self.call('force_price', product_id, direction, percent)

    def restore_one(self):
        product_id = self.selected_control_product()
        if product_id is not None and messagebox.askyesno('Restaurer ce produit', 'Rétablir maintenant son prix sauvegardé dans Fouaille ?', parent=self.root):
            self.call('restore_product', product_id)

    def interrupted_session(self):
        answer = messagebox.askyesnocancel(
            'Soirée interrompue retrouvée',
            'Les données locales et les prix d’origine ont été retrouvés.\n\nOui : continuer la soirée et conserver les compteurs.\nNon : restaurer tous les prix et terminer ; le prochain démarrage repartira de zéro.\nAnnuler : rester en pause.',
            parent=self.root,
        )
        if answer is True:
            self.call('pause')
        elif answer is False:
            self.call('finish')

    def start(self):
        if self.state['mode'] == 'mysql':
            count = sum(p['selected'] for p in self.state['products'])
            if not messagebox.askyesno('Activer les prix boursiers dans Fouaille', f'{count} boisson(s) sélectionnée(s).\n\nLes prix seront modifiés dans la base partagée et pourront être utilisés par les caisses Fouaille. Les tarifs d’origine seront sauvegardés avant toute écriture.\n\nVérifier les coûts par verre et arrêter les autres outils de modification des prix. Démarrer ?', parent=self.root):
                return
        self.call('start')

    def crash(self):
        if messagebox.askyesno('Confirmer le crash boursier', f"Déclencher maintenant une chute cible de {self.state['settings']['crash_drop']:g} %, suivie d’un rebond et d’un retour progressif ?\n\nLes limites de chaque boisson restent appliquées.", parent=self.root):
            self.call('crash')

    def finish(self):
        if messagebox.askyesno('Fin de soirée', 'Arrêter les variations et restaurer les prix d’origine de toutes les boissons sélectionnées ?\n\nEn mode Fouaille, arrêter d’abord les ventes en caisse pour clôturer le bilan.', parent=self.root):
            self.call('finish')

    def sale(self):
        selected = self.sale_tree.selection()
        if not selected:
            messagebox.showinfo('Vente', 'Sélectionner une boisson.', parent=self.root)
            return
        try:
            quantity = int(self.quantity.get())
            if not 1 <= quantity <= 1000:
                raise ValueError()
        except ValueError:
            messagebox.showerror('Quantité', 'Saisir un entier entre 1 et 1000.', parent=self.root)
            return
        self.call('manual_sale', int(selected[0]), quantity)

    def close(self):
        if self.busy:
            messagebox.showinfo('Opération en cours', 'Attendre la fin de l’opération avant de fermer.', parent=self.root)
            return
        if self.state and self.state['status'] in ('running', 'paused', 'recovery'):
            answer = messagebox.askyesnocancel('Fermer la régie', 'Restaurer les prix et terminer avant de quitter ?\n\nOui : fin de soirée et restauration.\nNon : sauvegarder et quitter en pause ; les prix actuels restent appliqués.\nAnnuler : revenir à la régie.', parent=self.root)
            if answer is None:
                return
            if answer:
                self.quitting = True
                self.call('finish')
                return
        self.call('quit')
