"""Two fresh new games started the same way: which orcs come out the same (story, fixed) and which differ (random)."""
import os, sys, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app', 'engine'))
sys.stdout.reconfigure(encoding='utf-8')
from sowtool import save as sv, orcs, ngplus
from sowtool.gamedata import GameData
gd = GameData(os.path.join(ROOT, 'app', 'gui', 'data', 'game.gamedb'), os.path.join(ROOT, 'app', 'gui', 'data', 'string_ruru.strdb'))
A, B = sys.argv[1:3]
def load(p):
    buf, uid = sv.load(p)
    print(os.path.basename(p), 'user %08x' % (uid or 0), 'Талион', sv.talion(buf), 'акт1', ngplus.act1_done(buf))
    return orcs.read(buf, gd)
a, b = load(A), load(B)
key = lambda o: (o['name'], o['title'], o['region'], o['place'], o['level'], o['tribe'], o['class'], tuple(sorted(o['traits'])), o['personality'])
slot = lambda o: (o['faction'], o['place_key'])
print('орков', len(a), len(b))
same = collections.Counter(map(key, a)) & collections.Counter(map(key, b))
print('полностью совпадают', sum(same.values()))
# by hierarchy slot
sa = {slot(o): o for o in a if o['place_key']}; sb = {slot(o): o for o in b if o['place_key']}
rows = collections.defaultdict(lambda: [0, 0])
for s in sorted(set(sa) | set(sb)):
    x, y = sa.get(s), sb.get(s)
    eq = x and y and key(x) == key(y)
    r = (x or y)['region']; pl = (x or y)['place']
    rows[(r, pl)][0 if eq else 1] += 1
    if not eq:
        f = lambda o: '%s %s ур%d %s' % (o['name'], o['title'], o['level'], 'сюжет' if o['story'] else '') if o else '—'
        print('  разные: %-12s %-10s | %s | %s' % (r, pl, f(x), f(y)))
print('\nпо местам (одинаковые / разные):')
for k, v in sorted(rows.items()):
    print('  %-14s %-12s %d / %d' % (k[0], k[1], v[0], v[1]))
# story orcs equal?
st = lambda L: sorted(key(o) for o in L if o['story'])
print('\nсюжетных', len(st(a)), len(st(b)), 'одинаковы' if st(a) == st(b) else 'РАЗНЫЕ')
pool = lambda L: sorted(key(o) for o in L if not o['place_key'])
print('без места (пул)', len(pool(a)), len(pool(b)), 'совпадают', sum((collections.Counter(pool(a)) & collections.Counter(pool(b))).values()))
