"""Experiment 28: a game save of experiment 27 (before the barrow mission) with the 6th Minas Morgul ithildin
added from the source - the whole set of the region at once, to see whether the barrow door and its verse break."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app', 'engine'))
sys.stdout.reconfigure(encoding='utf-8')
from sowtool import save as sv, ngplus, crypto
from sowtool.gamedata import GameData

gd = GameData(os.path.join(ROOT, 'app', 'gui', 'data', 'game.gamedb'), os.path.join(ROOT, 'app', 'gui', 'data', 'string_ruru.strdb'))
rec = gd.record
game = os.path.join(ROOT, 'game files', 'история', sys.argv[1])
buf = sv.load(game)[0]
source = sv.load(os.path.join(ROOT, 'game files', '096c2a9f_ShadowOfWarОРИГ.sav'))[0]
out = os.path.join(ROOT, 'game files', 'опыт орк 4 - Норско в иерархии', 'опыт 28 - все 6 итильдинов Минас-Моргула',
                   '096c2a9f_ShadowOfWar.sav')
name = 'Col_Lore_DoorClue_MinasIthil_06'
assert name in ngplus._picked(source, rec) and name not in ngplus._picked(buf, rec)
new = ngplus._take_records(buf, source, rec, [name])
new = ngplus._fix_iiuc(new, rec, [name])
new = ngplus.sync_region_counters(new, source, gd, ['ithildin'])
sv.validate(new, 'результат')
os.makedirs(os.path.dirname(out), exist_ok=True)
sv.write(out, new, crypto.user_id_from_name(out))
assert sv.load(out)[1] == 0x096c2a9f
for f in (game, out):
    b = sv.load(f)[0]
    m = ngplus.world_report(b, gd)['regions'][0]
    print(os.path.basename(f), 'Талион', sv.talion(b), 'башни', m['towers'], 'итильдин', m['ithildin'], '/', m['ithildin_total'],
          'счётчик', m['ithildin_counter'], 'дверь известно', m['door_known'], 'поставлено', m['door_placed'])
print(out)
