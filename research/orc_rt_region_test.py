"""Experiment 66: does RoleTransformation_Ambush («орк изменился») wait for its region, as CheatDeath_Ambush does.

    python research/orc_rt_region_test.py <live save> <source> <out folder>

On a copy of the finished game (all regions open): two living orcs of another player's save (no doubles of the
player's own orcs), level 70, by RoleTransformation_Ambush — one in Seregost at 1 minute, one in Gorgoroth at 1.5
minutes. The player stays where the save is for 3–5 minutes: if the ambushes stay in the queue ("now/waits") and come
when the player flies to their region, they wait; if they are removed, they do not (then the top orc of Nurn, alive,
cannot come by it on the prologue base).
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app', 'engine'))
sys.path.insert(0, os.path.join(ROOT, 'research'))
from sowtool import crypto, orcs, save as sv                # noqa: E402
from sowtool.gamedata import GameData                       # noqa: E402
import orc_ambush20                                         # noqa: E402
import orc_ghosts                                           # noqa: E402

LEVEL = 70
PLAN = [('Faction_snowMtn', 'Серегост', 60), ('Faction_volcano', 'Горгорот', 90)]


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    live_p, src_p, out_dir = sys.argv[1:4]
    gd = GameData(os.path.join(ROOT, 'app', 'gui', 'data', 'game.gamedb'),
                  os.path.join(ROOT, 'app', 'gui', 'data', 'string_ruru.strdb'))
    live, source = sv.load(live_p)[0], sv.load(src_p)[0]
    pairs = {(o['name'], o['title']) for o in orcs.read(live, gd)}
    living = [o for o in orcs.read(source, gd)
              if not o['dead'] and not o['follower'] and not o['story'] and o['class'] != 'олог'
              and (o['name'], o['title']) not in pairs and o['title']]
    living.sort(key=lambda o: o['level'], reverse=True)
    real = orc_ghosts.prepare

    def prepare(raw, number, region, reward, rec_, day=1):
        raw, src_region, days = real(raw, number, region, reward, rec_, day)
        return orc_ambush20.fix(raw, rec_, None, LEVEL, False, True), src_region, days
    orc_ghosts.prepare = prepare
    out = live
    for (faction, name, sec), o in zip(PLAN, living):
        out = bytes(orc_ghosts.build(out, source, [(o['number'], '@RoleTransformation_Ambush')], faction, gd,
                                     log=lambda *a: None, first=sec * 1000, step=1))
        print('через %d с  %s: %s %s, ур. %d' % (sec, name, o['name'], o['title'], LEVEL))
    sv.validate(out, 'результат')
    os.makedirs(out_dir, exist_ok=True)
    out_p = os.path.join(out_dir, '096c2a9f_ShadowOfWar.sav')
    sv.write(out_p, out, crypto.user_id_from_name(out_p))
    assert sv.load(out_p)[1] == 0x096c2a9f
    print('Записано:', out_dir)


if __name__ == '__main__':
    main()
