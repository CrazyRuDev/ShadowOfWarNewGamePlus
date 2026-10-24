"""Orcs of a save by what they have to do with Talion (research).

Direct: the orc met Talion (threat, showdown, fight, killed him or was killed by him, last chance, fled,
domination...). Indirect: only heard of him — events about Talion without meeting (a blood brother killed by him, a
follower's betrayal...). None: nothing about Talion.

    python research/orc_memory.py <save>
"""
import collections
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app', 'engine'))
sys.path.insert(0, os.path.join(ROOT, 'research'))
from sowtool import save as sv                        # noqa: E402
from sowtool.gamedata import GameData                 # noqa: E402
import orc_days                                       # noqa: E402
import orc_insert                                     # noqa: E402
import orcs2                                          # noqa: E402

DIRECT = ('ActiveInitialPlayerThreat', 'ActiveShowdownGiven', 'ActiveKillPlayer', 'ActiveGotPlayerInLastChance',
          'ArcherPutsPlayerInLastChance', 'ActiveKilledByPlayer', 'ActiveSurvivedVsPlayer', 'ActiveFlee',
          'ActiveDominationStarted', 'Domination_', 'ActiveReverseLastChance', 'ActiveRevivedByPlayer',
          'IsPlayerFollower', 'BecomeBodyguardToPlayer', 'ActiveIdentify', 'ActiveGainInterrogationIntel',
          'ActiveSetInterrogationSubject', 'Resurrection_Player', 'WillResurrect_Player')


def kind(ev):
    if any(ev.startswith(d) for d in DIRECT):
        return 'direct'
    if 'Player' in ev or 'Talion' in ev:
        return 'indirect'
    return None


def classify(buf, gd):
    rec = gd.record
    p, t, mg, n, starts, end = orc_insert.table(buf, rec)
    out = []
    for o in orcs2.orcs(buf, gd):
        num = o.get('number')
        if num is None or orcs2.story_reasons(o):
            continue
        ev = [rec(t[i - 1].value) for i in orc_days.history(t, starts, end, num, rec)]
        direct = [e for e in ev if kind(e) == 'direct']
        indirect = [e for e in ev if kind(e) == 'indirect']
        met = bool(direct) or 'PresentedToPlayer' in o['flags']
        out.append(dict(o=o, met=met, direct=direct, indirect=indirect, level=o['ints'][3] + 1))
    return out


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    gd = GameData(os.path.join(ROOT, 'app', 'gui', 'data', 'game.gamedb'),
                  os.path.join(ROOT, 'app', 'gui', 'data', 'string_ruru.strdb'))
    buf, _ = sv.load(sys.argv[1])
    rows = classify(buf, gd)
    met = [r for r in rows if r['met']]
    heard = [r for r in rows if not r['met'] and r['indirect']]
    none = [r for r in rows if not r['met'] and not r['indirect']]
    st = lambda r: 'мёртв' if 'IsDead' in r['o']['flags'] else ('последователь' if 'PlayerFollower' in r['o']['flags'] else 'враг')  # noqa: E731
    print('не сюжетных орков: %d — встречались с Талионом: %d, только «слышали» о нём: %d, ничего: %d'
          % (len(rows), len(met), len(heard), len(none)))
    for title, group in (('встречались', met), ('слышали', heard), ('ничего', none)):
        c = collections.Counter(st(r) for r in group)
        lv = sorted(r['level'] for r in group)
        print('  %-11s %s; уровни %s…%s' % (title, dict(c), lv[0] if lv else '-', lv[-1] if lv else '-'))
    print('\nТолько «слышали» о Талионе:')
    for r in sorted(heard, key=lambda r: -r['level']):
        o = r['o']
        print('  №%-4d %-30s ур.%-3d %-13s %s' % (o['number'], o.get('name', '?') + ' ' + orcs2.title(gd, o['role']), r['level'],
                                                st(r), dict(collections.Counter(r['indirect']))))
