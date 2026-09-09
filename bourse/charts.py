"""Tracé commun des cours ; ne dépend ni de la régie ni de la base."""
from collections import defaultdict
from datetime import datetime

MUTED = '#97aac4'


def draw_price_chart(canvas, products, history, empty_text='Les cours seront bientôt disponibles.'):
    canvas.delete('all')
    w, h = max(200, canvas.winfo_width()), max(70, canvas.winfo_height())
    left, right, top, bottom = 76, w - 48, 22, h - 35
    ids = {p['id'] for p in products}
    series = defaultdict(list)
    for point in history:
        if point['product_id'] in ids:
            series[point['product_id']].append(point)
    series = {pid: points[-120:] for pid, points in series.items()}
    all_points = [point for points in series.values() for point in points]
    if not all_points:
        canvas.create_text(w / 2, h / 2, text=empty_text, fill=MUTED,
                           font=('Helvetica', 14), justify='center', width=max(120, w - 80))
        return
    lo = max(0, min(p['price'] for p in all_points) * .85)
    hi = max(max(p['price'] for p in all_points) * 1.15, lo + 100)
    times = sorted({p['at'] for p in all_points})
    t0 = datetime.fromisoformat(times[0]).timestamp()
    t1 = datetime.fromisoformat(times[-1]).timestamp()

    def x(stamp):
        return left + (datetime.fromisoformat(stamp).timestamp() - t0) / max(1, t1 - t0) * (right - left)

    def y(price):
        return bottom - (price - lo) / (hi - lo) * (bottom - top)

    for i in range(5):
        price = lo + (hi - lo) * i / 4
        yy = y(price)
        canvas.create_line(left, yy, right, yy, fill='#23334c')
        canvas.create_text(left - 9, yy, text=f'{price / 100:.2f} €'.replace('.', ','),
                           fill=MUTED, anchor='e', font=('Helvetica', 10))
    for index in sorted({0, len(times) // 2, len(times) - 1}):
        stamp = times[index]
        canvas.create_text(x(stamp), bottom + 20,
                           text=datetime.fromisoformat(stamp).strftime('%H:%M:%S'),
                           fill=MUTED, font=('Helvetica', 10))
    for p in products:
        points = series.get(p['id'], [])
        coords = [coordinate for point in points for coordinate in (x(point['at']), y(point['price']))]
        if len(coords) >= 4:
            canvas.create_line(*coords, fill=p['color'], width=2.5)
        if coords:
            xx, yy = coords[-2:]
            canvas.create_oval(xx - 4, yy - 4, xx + 4, yy + 4, fill=p['color'], outline='')
