"""What else the game changes in an orc on a return from the dead, besides looks (research).

    python research/return_traits.py

Goes through the history saves like scar_looks.py and, for every dead → alive IsResurrected transition, prints the
added and removed traits (Picker_*), markers (*Marker*, ET_*), role, level and the reward it had.
"""
import glob
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app', 'engine'))
from sowtool import army, orcs, save as sv     # noqa: E402
from sowtool.gamedata import GameData            # noqa: E402


def traits(buf, tab, num, rec):
    a, b = army._record(buf, *tab, num)
    tt = sv.tokens(buf[a:b], 0, b - a)
    names = (rec(x.value) for x in tt if x.type == 0 and x.value is not None)
    return {n for n in names if n and (n.startswith(('Picker_', 'ET_')) or 'Marker' in n)}


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    gd = GameData(os.path.join(ROOT, 'app', 'gui', 'data', 'game.gamedb'),
                  os.path.join(ROOT, 'app', 'gui', 'data', 'string_ruru.strdb'))
    rec = gd.record
    prev, seen = None, set()
    for f in sorted(glob.glob(os.path.join(ROOT, 'game files', 'история', '*.sav'))):
        try:
            buf = sv.load(f)[0]
            now = {o['number']: o for o in orcs.read(buf, gd)}
        except Exception:
            continue
        if prev:
            pbuf, pnow = prev
            for n, o in now.items():
                p = pnow.get(n)
                if not p or p['name'] != o['name'] or not p['dead'] or o['dead'] or 'IsResurrected' not in o['flags']:
                    continue
                key = (o['name'], tuple(p['rewards']))
                if key in seen:
                    continue
                seen.add(key)
                before = traits(pbuf, army._table(pbuf, rec), n, rec)
                after = traits(buf, army._table(buf, rec), n, rec)
                print('%s %s %s: %s -> %s, ур. %s -> %s, награда %s, гибель %s'
                      % (os.path.basename(f)[-19:-4], o['name'], o['title'], p['role_key'], o['role_key'],
                         p['level'], o['level'], p['rewards'], p['death_cause']))
                print('    +', sorted(after - before))
                print('    -', sorted(before - after))
        prev = (buf, now)


if __name__ == '__main__':
    main()
