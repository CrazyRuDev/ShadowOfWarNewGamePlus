"""Watches the Shadow of War save while you play: every version the game writes is copied to a history folder
and compared with the previous one (level, skill points, skills, stock table, items, equipment, changed blocks).

    python tools/watch_saves.py [--save <file>] [--out <folder>] [--data <folder>]

Only reads and copies the save, never writes to it. Stop with Ctrl+C.
"""
import argparse
import datetime
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app', 'engine'))
sys.path.insert(0, os.path.join(ROOT, 'research'))

from sowtool import save as sv, steam            # noqa: E402
from sowtool.gamedata import GameData            # noqa: E402
import queue as nemesis_queue                     # noqa: E402  research/queue.py (Nemesis event queue)


class Snapshot:
    def __init__(self, buf, gd):
        rec = lambda r: gd.record(r) or '#%08x' % r                       # noqa: E731
        self.buf = buf
        self.level, self.xp = sv.talion(buf)
        inv = sv.Inventory(buf)
        self.stock = {rec(r): c for r, c, *_ in inv.stock}
        learned = sv.unlocks(buf)
        self.ivpd = {rec(r): v for r, v in learned.items()}
        self.items = {it['uid']: (it['level'], rec(it['template'])) for it in inv.items}
        self.equipped = list(inv.equipped)
        self.sockets = [(rec(s), rec(g) if g else None) for s, g in inv.sockets]
        self.blocks = {}
        for k in range(len(sv.sections(buf))):
            for tag, _, p, size in sv.blocks(buf, k):
                self.blocks['%d:%s' % (k, tag)] = buf[p:p + 16 + size]
        try:
            self.queue = nemesis_queue.queue(buf, gd)
        except Exception:                          # noqa: BLE001 - the queue is only a debugging aid
            self.queue = []


def queue_diff(a, b):
    """The Nemesis queue when its set of events changed: what appeared, what left, and the whole queue."""
    key = lambda q: [(e[0], e[1], e[2]) for e in q]                     # noqa: E731
    if a is not None and key(a.queue) == key(b.queue):
        return []
    old, new = (key(a.queue) if a else []), key(b.queue)
    out = []
    for ev, reg, num, name, tag, ms in b.queue:
        if (ev, reg, num) not in old:
            out.append('Очередь: + %s %s %s' % (ev, reg, ('№%d %s' % (num, name)) if num >= 0 else ''))
    for ev, reg, num, name, tag, ms in (a.queue if a else []):
        if (ev, reg, num) not in new:
            out.append('Очередь: − %s %s %s (сработало или снято)' % (ev, reg, ('№%d %s' % (num, name)) if num >= 0 else ''))
    for ev, reg, num, name, tag, ms in sorted(b.queue, key=lambda e: e[5]):
        out.append('  через %-8s %-34s %-13s %s' % (nemesis_queue.fmt(ms), ev, reg, ('№%d %s' % (num, name)) if num >= 0 else ''))
    return out


def diff(a, b):
    out = queue_diff(a, b)
    if (a.level, a.xp) != (b.level, b.xp):
        out.append('Уровень/опыт: %s/%s -> %s/%s' % (a.level, a.xp, b.level, b.xp))

    def changes(title, x, y, limit=40):
        lines = []
        for k in sorted(set(x) | set(y)):
            if x.get(k) != y.get(k):
                lines.append('  %s: %s -> %s' % (k, x.get(k, '-'), y.get(k, '-')))
        if lines:
            out.append('%s (%d):' % (title, len(lines)))
            out.extend(lines[:limit] + (['  … ещё %d' % (len(lines) - limit)] if len(lines) > limit else []))
    changes('Таблица запасов IVMG', a.stock, b.stock)
    changes('Разблокировки IVPD', a.ivpd, b.ivpd)
    gone = [u for u in a.items if u not in b.items]
    new = [u for u in b.items if u not in a.items]
    lvl = [u for u in b.items if u in a.items and a.items[u] != b.items[u]]
    for title, uids, src in (('Новые предметы', new, b), ('Пропали предметы', gone, a), ('Изменились', lvl, b)):
        if uids:
            out.append('%s: %s' % (title, ', '.join('№%d %s ур.%d' % (u, src.items[u][1], src.items[u][0])
                                                     for u in uids)))
    if a.equipped != b.equipped:
        out.append('Экипировка: %s -> %s' % (a.equipped, b.equipped))
    if a.sockets != b.sockets:
        out.append('Слоты самоцветов: %s' % [s for s in b.sockets if s not in a.sockets])
    changed = [k for k in b.blocks if a.blocks.get(k) != b.blocks[k]]
    sizes = ['%s %+d' % (k, len(b.blocks[k]) - len(a.blocks.get(k, b''))) for k in changed]
    out.append('Изменённые блоки (%d): %s' % (len(changed), ', '.join(sizes) or '-'))
    return out


def write_overlay(path, snap, saved, changes, name):
    """Data for tools/overlay.ahk, tab-separated, UTF-8:
    saved <unix ms of the save> <copy name> | event <ms left> <event> <description> <region> <orc> | change <time> <text>"""
    def clean(s):
        return str(s).replace('\t', ' ').replace('\n', ' ')
    rows = ['saved\t%d\t%s\t%s\t%s' % (int(saved * 1000), clean(name), snap.level, snap.stock.get('PC_Mirian', 0))]
    for ev, reg, num, orc, tag, ms in sorted(snap.queue, key=lambda e: e[5]):
        rows.append('event\t%d\t%s\t%s\t%s\t%s' % (ms, clean(ev), clean(nemesis_queue.describe(ev)), clean(reg),
                                                   clean(('№%d %s' % (num, orc)) if num >= 0 else '')))
    for t, text in changes:
        rows.append('change\t%s\t%s' % (t, clean(text)))
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write('\n'.join(rows) + '\n')
    os.replace(tmp, path)                              # the overlay never sees a half-written file


def stable_read(path):
    """File contents once the game has finished writing it (size and time unchanged for a moment)."""
    while True:
        st = os.stat(path)
        time.sleep(0.3)
        st2 = os.stat(path)
        if (st.st_size, st.st_mtime) == (st2.st_size, st2.st_mtime):
            return open(path, 'rb').read(), st2.st_mtime


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--save', help='save file to watch (default: the newest Steam save)')
    ap.add_argument('--out', default=os.path.join(ROOT, 'game files', 'история'))
    ap.add_argument('--data', default=os.path.join(ROOT, 'app', 'gui', 'data'))
    args = ap.parse_args()
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8')
        except (AttributeError, ValueError):
            pass
    path = args.save or steam.find_save()
    if not path or not os.path.exists(path):
        sys.exit('Сохранение не найдено — укажите --save <файл>')
    os.makedirs(args.out, exist_ok=True)
    gd = GameData(os.path.join(args.data, 'game.gamedb'), os.path.join(args.data, 'string_ruru.strdb'))
    log_path = os.path.join(args.out, 'журнал.txt')
    stem = os.path.basename(path)[:-len('.sav')]

    def log(lines):
        with open(log_path, 'a', encoding='utf-8') as f:
            for line in lines:
                print(line, flush=True)
                f.write(line + '\n')

    log(['', '=== %s: слежу за %s' % (datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), path)])
    prev, last_mtime, changes = None, None, []
    while True:
        try:
            mtime = os.path.getmtime(path)
            if mtime != last_mtime:
                raw, last_mtime = stable_read(path)
                stamp = datetime.datetime.fromtimestamp(last_mtime).strftime('%Y%m%d-%H%M%S')
                copy = os.path.join(args.out, '%s_%s.sav' % (stem, stamp))   # keeps <id>_ShadowOfWar in the name
                if not os.path.exists(copy):
                    with open(copy, 'wb') as f:
                        f.write(raw)
                try:
                    buf, _ = sv.load(copy)
                    snap = Snapshot(buf, gd)
                except Exception as e:                       # noqa: BLE001
                    log(['%s: не удалось разобрать (%s: %s)' % (os.path.basename(copy), type(e).__name__, e)])
                else:
                    head = '--- %s  уровень %s, мирианы %s, очки навыков %s' % (
                        os.path.basename(copy), snap.level, snap.stock.get('PC_Mirian', 0),
                        snap.stock.get('SkillPoint', 0))
                    lines = diff(prev, snap) if prev else ['(первая копия)'] + queue_diff(None, snap)
                    log([head] + lines)
                    now = datetime.datetime.now().strftime('%H:%M:%S')
                    changes.extend((now, x[len('Очередь: '):]) for x in lines if x.startswith('Очередь: '))
                    del changes[:-12]
                    write_overlay(os.path.join(args.out, 'оверлей.txt'), snap, last_mtime, changes, os.path.basename(copy))
                    prev = snap
            time.sleep(0.5)
        except KeyboardInterrupt:
            break
        except OSError:                                      # the game is replacing the file right now
            time.sleep(0.5)


if __name__ == '__main__':
    main()
