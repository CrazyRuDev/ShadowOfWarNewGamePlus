"""Experiment 27: prologue base, everything of Minas Morgul transferred (ithildin, its region counters) except its
towers (hadirs) - the story has the player take one there. Same as the full transfer of experiment 26 otherwise.
The engine keeps Minas Morgul untouched before act 1; here add_collectibles runs as if act 1 were done."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app', 'engine'))
sys.stdout.reconfigure(encoding='utf-8')
from sowtool import save as sv, ngplus, crypto
from sowtool.gamedata import GameData

gd = GameData(os.path.join(ROOT, 'app', 'gui', 'data', 'game.gamedb'), os.path.join(ROOT, 'app', 'gui', 'data', 'string_ruru.strdb'))
base = sv.load(os.path.join(ROOT, 'app', 'gui', 'bases', 'prologue_ShadowOfWar.sav'))[0]
source = sv.load(os.path.join(ROOT, 'game files', '096c2a9f_ShadowOfWarОРИГ.sav'))[0]
out = os.path.join(ROOT, 'game files', 'опыт орк 4 - Норско в иерархии', 'опыт 27 - пролог, Минас-Моргул весь кроме хэдиров',
                   '096c2a9f_ShadowOfWar.sav')

orig_add, orig_act1 = ngplus.add_collectibles, ngplus.act1_done
def add_all(*a, **k):
    ngplus.act1_done = lambda buf: True        # collectibles only: Minas Morgul too
    try:
        return orig_add(*a, **k)
    finally:
        ngplus.act1_done = orig_act1
ngplus.add_collectibles = add_all

new = ngplus.build(base, source, gd, towers=True, collect=['ithildin', 'gondor', 'shelob'],
                   start=True, clean=True, story=True)
sv.validate(new, 'результат')
os.makedirs(os.path.dirname(out), exist_ok=True)
sv.write(out, new, crypto.user_id_from_name(out))
assert sv.load(out)[1] == 0x096c2a9f
w = ngplus.world_report(sv.load(out)[0], gd)
for r in w['regions']:
    print(r['region'], 'башни', r['towers'], 'итильдин', r['ithildin'], '/', r['ithildin_total'],
          'дверь', r['door_known'], 'счётчики', r['ithildin_counter'], r['gondor'], r['shelob'])
print([(c['title'], c['have']) for c in w['collections']])
print(out)
