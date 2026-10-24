"""What the game changes in an orc's looks when it comes back from the dead with a scar reward (research).

    python research/scar_looks.py

Goes through the history saves (game files/история), follows every orc between consecutive saves and, when it
turns from dead to alive with IsResurrected, prints the reward it had, the role it got and the looks records
(items AD_*/IT_*, models Orc_*, the voice Orc_<Personality>N) that were added and removed. Used to give "came back
beforehand" orcs the same looks without the game's resurrection event.
"""
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app', 'engine'))
from sowtool import army, orcs, save as sv     # noqa: E402
from sowtool.gamedata import GameData            # noqa: E402

LOOKS = re.compile(r'^(AD_|IT_|Orc_|Tag_|ScarBookmark_)|Scar|Prosth|Sack|Bandage')


def looks(buf, t, starts, end, num, rec):
    a, b = army._record(buf, t, starts, end, num)
    tt = sv.tokens(buf[a:b], 0, b - a)
    return {rec(x.value) for x in tt if x.type == 0 and rec(x.value) and LOOKS.search(rec(x.value))}


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    gd = GameData(os.path.join(ROOT, 'app', 'gui', 'data', 'game.gamedb'),
                  os.path.join(ROOT, 'app', 'gui', 'data', 'string_ruru.strdb'))
    rec = gd.record
    prev, seen = None, set()
    for f in sorted(glob.glob(os.path.join(ROOT, 'game files', 'история', '*.sav'))):
        try:
            buf = sv.load(f)[0]
            army_ = {o['number']: o for o in orcs.read(buf, gd)}
        except Exception:
            continue
        if prev:
            pbuf, parmy = prev
            for n, o in army_.items():
                p = parmy.get(n)
                if not p or p['name'] != o['name'] or not p['dead'] or o['dead'] or 'IsResurrected' not in o['flags']:
                    continue
                key = (o['name'], tuple(p['rewards']))
                if key in seen:
                    continue
                seen.add(key)
                pt = army._table(pbuf, rec)
                nt = army._table(buf, rec)
                before, after = looks(pbuf, *pt, n, rec), looks(buf, *nt, n, rec)
                print('%s  %s %s: %s -> %s, награда %s' % (os.path.basename(f)[-19:-4], o['name'], o['title'],
                                                           p['role_key'], o['role_key'], p['rewards']))
                print('    +', sorted(after - before))
                print('    -', sorted(before - after))
        prev = (buf, army_)


if __name__ == '__main__':
    main()
