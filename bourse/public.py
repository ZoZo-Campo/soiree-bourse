"""Écran spectateurs : uniquement prix, pourcentages et courbes.

Aucune commande de vente, réglage, cagnotte ou connexion n'entre dans cet écran.
"""
import tkinter as tk
from .charts import draw_price_chart

BG, PANEL, TEXT, MUTED = '#0b1220', '#111e31', '#e7eefb', '#97aac4'
PAGE_SIZE = 6
PAGE_INTERVAL_MS = 12000


def public_snapshot(state):
    """Liste blanche : aucun champ interne ni message d'erreur n'est transmis."""
    unavailable = state['status'] == 'recovery'
    ready = state['status'] == 'ready'
    if unavailable or ready:
        return {'products': [], 'history': [], 'message': (
            'Cours momentanément indisponibles.' if unavailable else 'Les cours seront bientôt disponibles.')}
    products = [
        {key: p[key] for key in ('id', 'name', 'price', 'previous', 'color')}
        for p in state['products'] if p['selected']
    ]
    ids = {p['id'] for p in products}
    history = [
        {key: point[key] for key in ('at', 'product_id', 'price')}
        for point in state.get('history', []) if point['product_id'] in ids
    ]
    return {'products': products, 'history': history, 'message': ''}


class PublicDisplay:
    """Fenêtre indépendante à déplacer sur le projecteur en bureau étendu."""
    def __init__(self, parent):
        self.window = tk.Toplevel(parent)
        self.window.title('Soirée Bourse · Cours & prix')
        self.window.configure(bg=BG)
        self.window.geometry('1180x740+70+70')
        self.window.minsize(760, 600)
        self.window.protocol('WM_DELETE_WINDOW', self.close)
        self.window.bind('<Escape>', lambda _: self.window.attributes('-fullscreen', False))
        self.data = {'products': [], 'history': [], 'message': 'Les cours seront bientôt disponibles.'}
        self.page, self.columns, self.product_ids = 0, 0, ()
        self.closed, self.timer = False, None
        self.cards = []
        outer = tk.Frame(self.window, bg=BG, padx=26, pady=22)
        outer.pack(fill='both', expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(3, weight=1)
        heading = tk.Frame(outer, bg=BG)
        heading.grid(row=0, column=0, sticky='ew', pady=(0, 16))
        tk.Label(heading, text='SOIRÉE BOURSE', bg=BG, fg=TEXT,
                 font=('Helvetica', 27, 'bold')).pack(side='left')
        self.page_label = tk.Label(heading, text='COURS & PRIX', bg=BG, fg=MUTED,
                                   font=('Helvetica', 12, 'bold'))
        self.page_label.pack(side='right')
        self.cards_box = tk.Frame(outer, bg=BG)
        self.cards_box.grid(row=1, column=0, sticky='ew')
        self.message = tk.Label(outer, text='', bg=BG, fg=MUTED, font=('Helvetica', 17), pady=12)
        self.message.grid(row=2, column=0, sticky='ew')
        self.canvas = tk.Canvas(outer, bg=PANEL, highlightthickness=0, height=260)
        self.canvas.grid(row=3, column=0, sticky='nsew')
        self.canvas.bind('<Configure>', lambda _: self.draw())
        self.cards_box.bind('<Configure>', self.resize_cards)
        self.timer = self.window.after(PAGE_INTERVAL_MS, self.next_page)
        self.window.bind('<Destroy>', self.destroyed, add='+')

    def destroyed(self, event):
        if event.widget is self.window:
            self.closed = True
            if self.timer is not None:
                try:
                    self.window.after_cancel(self.timer)
                except tk.TclError:
                    pass
                self.timer = None

    def close(self):
        # Fermer cet écran ne ferme pas la régie et ne change pas les prix.
        self.window.destroy()

    def fullscreen(self):
        self.window.attributes('-fullscreen', not bool(self.window.attributes('-fullscreen')))

    def render(self, data):
        self.data = data
        ids = tuple(p['id'] for p in data['products'])
        if ids != self.product_ids:
            self.page = 0
            self.product_ids = ids
        self.update_cards()
        self.draw()

    def page_products(self):
        return self.data['products'][self.page * PAGE_SIZE:(self.page + 1) * PAGE_SIZE]

    def resize_cards(self, event):
        columns = 3 if event.width >= 1000 else 2
        if columns != self.columns:
            self.columns = columns
            self.update_cards()

    def update_cards(self):
        products = self.page_products()
        # Les cartes restent en place entre deux mouvements pour éviter le scintillement.
        if len(self.cards) != len(products):
            for child in self.cards_box.winfo_children():
                child.destroy()
            self.cards = []
            for _ in products:
                box = tk.Frame(self.cards_box, bg=PANEL, padx=16, pady=12)
                name = tk.Label(box, bg=PANEL, fg=TEXT, font=('Helvetica', 15, 'bold'), anchor='w')
                name.pack(fill='x')
                bottom = tk.Frame(box, bg=PANEL)
                bottom.pack(fill='x', pady=(5, 0))
                price = tk.Label(bottom, bg=PANEL, fg=TEXT, font=('Helvetica', 32, 'bold'))
                price.pack(side='left')
                change = tk.Label(bottom, bg=PANEL, font=('Helvetica', 17, 'bold'))
                change.pack(side='right')
                self.cards.append((box, name, price, change))
        columns = self.columns or 3
        for col in range(3):
            self.cards_box.columnconfigure(col, weight=1 if col < columns else 0, uniform='prices' if col < columns else '')
        for i, (p, (box, name, price, change)) in enumerate(zip(products, self.cards)):
            box.grid(row=i // columns, column=i % columns, sticky='nsew', padx=(0, 8), pady=(0, 8))
            name.configure(text='● ' + p['name'], fg=p['color'], wraplength=max(180, self.cards_box.winfo_width() // columns - 50))
            price.configure(text=f"{p['price'] / 100:.2f} €".replace('.', ','))
            diff = (p['price'] / p['previous'] - 1) * 100 if p['previous'] else 0
            change.configure(text=f'{diff:+.1f} %'.replace('.', ','),
                             fg='#34d399' if diff > 0 else '#fb7185' if diff < 0 else MUTED)
        pages = max(1, (len(self.data['products']) + PAGE_SIZE - 1) // PAGE_SIZE)
        self.page_label.configure(text='COURS & PRIX' + (f'  ·  {self.page + 1}/{pages}' if pages > 1 else ''))
        self.message.configure(text=self.data['message'] or 'Prix du verre · variation depuis le dernier cours')

    def next_page(self):
        if self.closed:
            return
        pages = max(1, (len(self.data['products']) + PAGE_SIZE - 1) // PAGE_SIZE)
        if pages > 1:
            self.page = (self.page + 1) % pages
            self.update_cards()
            self.draw()
        self.timer = self.window.after(PAGE_INTERVAL_MS, self.next_page)

    def draw(self):
        if not self.closed:
            draw_price_chart(self.canvas, self.page_products(), self.data['history'], empty_text='')
