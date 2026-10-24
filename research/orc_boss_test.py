"""Experiment 63: a boss and the queue (research).

    python research/orc_boss_test.py <live save> <source> <out>

On the player's own save: the waiting "cheated death" events of earlier experiments taken out, then
  1 min — "cheated death" of an orc in Gorgoroth: it should wait there (the player is in Nurn);
  2 min — a boss in Nurn: the most killing orc of the source not in the save yet, level 45, every weakness and fear
          off, the resistances replaced by BOSS immunities, the BOSS traits added;
  4 min — an ordinary "cheated death" in Nurn, level 37.
If the Nurn ones come while the Gorgoroth one waits, a boss far away does not hold the queue.
"""
import os
import random
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app', 'engine'))
sys.path.insert(0, os.path.join(ROOT, 'research'))
from sowtool import crypto, orcs, returned, save as sv     # noqa: E402
from sowtool.gamedata import GameData                       # noqa: E402
import orc_ambush20                                         # noqa: E402
import orc_ambush_long                                      # noqa: E402
import orc_ghosts                                           # noqa: E402

BOSS = ['Picker_NoLastChance', 'Picker_IronWill', 'Picker_SecondWind', 'Picker_Determination', 'Picker_Deadly',
        'Picker_Fearless', 'Picker_Resist_Stealth_Immune', 'Picker_Resist_Ranged_Immune', 'Picker_Resist_Poison_Immune',
        'Picker_Resist_Fire_Immune', 'Picker_Resist_Curse_Immune', 'Picker_OrcRarity_Legendary']
REPLACED = ('Picker_Resist_Stealth_', 'Picker_Resist_Ranged_', 'Picker_Resist_Poison_', 'Picker_Resist_Fire_',
            'Picker_Resist_Curse_', 'Picker_Fearless', 'Picker_OrcRarity_')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    live_p, src_p, out_p = sys.argv[1:4]
    gd = GameData(os.path.join(ROOT, 'app', 'gui', 'data', 'game.gamedb'),
                  os.path.join(ROOT, 'app', 'gui', 'data', 'string_ruru.strdb'))
    rec = gd.record
    live, source = sv.load(live_p)[0], sv.load(src_p)[0]
    orc_ambush_long.OLD = range(377, 440)
    live, gone = orc_ambush_long.drop_old(live, rec)
    print('Из очереди убраны ждущие засады прошлых опытов:', gone)
    orcs.MIN_SCORE = 1                            # every orc that met Talion: those of score 5+ are in the save already
    live_orcs = orcs.read(live, gd)                # names repeat: ours (added from 377 on) by name, others by title
    have = {o['name'] for o in live_orcs if o['number'] >= 377}
    pairs = {(o['name'], o['title']) for o in live_orcs}
    killed = [o for o in orcs.recommend(orcs.read(source, gd), total=80)
              if o['dead'] and o['killer_name'] == 'Талион' and o['name'] not in have
              and (o['name'], o['title']) not in pairs
              and 'HeadRemoved' not in o['death_cause'] and 'Dopple' not in o['role_key'] and o['class'] != 'олог']
    boss = max(killed, key=lambda o: (o['kill'], o['danger']))
    rest = [o for o in killed if o is not boss]
    plan = [('Faction_volcano', rest[0], 60, 40, False), ('Faction_island', boss, 120, 45, True),
            ('Faction_island', rest[1], 240, 37, False)]
    out, lines = live, []
    real_prepare = orc_ghosts.prepare
    for region, o, sec, level, is_boss in plan:
        s = returned.comes_back(o)

        def prepare(raw, number, region_, reward, rec_, day=1, s=s, level=level, is_boss=is_boss):
            raw, src_region, days = real_prepare(raw, number, region_, reward, rec_, day)
            raw = orc_ambush20.fix(raw, rec_, returned.SCARS[s][0], level, False, False)
            raw, _ = returned.looks(raw, s, rec_)
            if is_boss:
                raw, _ = returned.remove_traits(raw, lambda n: returned.WEAK['all'][1](n) or n.startswith(REPLACED),
                                                rec_)
                raw = returned.add_traits(raw, BOSS, returned.LEGEND, rec_)
            return raw, src_region, days
        orc_ghosts.prepare = prepare
        reward = returned.REWARDS.get(s, 'ResReward_PinnicleScar_' + s)
        out = bytes(orc_ghosts.build(out, source, [(o['number'], reward)], region, gd, log=lambda *a: None,
                                     first=sec * 1000, step=1))
        lines.append('через %d мин  %-9s %s %s — %s, ур. %d%s' % (
            sec // 60, orcs.REGIONS[region], o['name'], o['title'], returned.TITLES[s], level,
            ', БОСС (убил Талиона %d раз)' % o['kill'] if is_boss else ''))
    sv.validate(out, 'результат')
    os.makedirs(os.path.dirname(os.path.abspath(out_p)), exist_ok=True)
    sv.write(out_p, out, crypto.user_id_from_name(out_p))
    assert sv.load(out_p)[1] == 0x096c2a9f
    for s in lines:
        print(s)
    print('Записано:', out_p)


if __name__ == '__main__':
    main()
