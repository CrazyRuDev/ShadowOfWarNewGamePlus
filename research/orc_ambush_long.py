"""Experiment 62: long ambush timers and the time skip at a tower (research).

    python research/orc_ambush_long.py <live save> <source> <out>

On the player's own save (after experiment 61): the "cheated death" and betrayal events still waiting in the queue
for the orcs of experiment 61 are taken out (they come one at a time and would hold the new ones back). Then 4
"cheated death" (killed by Talion, after the twenty by rating, no severed head, no doubles), with the looks of their
return written in beforehand (returned.looks), and 2 "the orc changed" (living or killed by orcs), level 40-50.
Timers in minutes of game time: CD 1, 20, 35, 50; RT 15, 42.
"""
import os
import random
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app', 'engine'))
sys.path.insert(0, os.path.join(ROOT, 'research'))
from sowtool import crypto, orcs, returned, save as sv     # noqa: E402
from sowtool.gamedata import GameData, name_hash            # noqa: E402
import orc_ambush20                                         # noqa: E402
import orc_ghosts                                           # noqa: E402

PLAN = [(1, 'CheatDeath_Ambush'), (15, 'RoleTransformation_Ambush'), (20, 'CheatDeath_Ambush'),
        (35, 'CheatDeath_Ambush'), (42, 'RoleTransformation_Ambush'), (50, 'CheatDeath_Ambush')]
OLD = range(377, 397)                         # the orcs of experiment 61


def drop_old(buf, rec):
    """The waiting CheatDeath_* events of the orcs of experiment 61 out of the queue."""
    t = sv.block_tokens(buf, 'WHDC')
    q = [i for i in range(len(t) - 7) if t[i].type == 0x0C and t[i].value == 1 and t[i + 1].type == 0
         and (rec(t[i + 1].value) or '').startswith('Faction_') and t[i + 2].type == 0 and t[i + 3].type == 0
         and t[i + 4].type == 4 and t[i + 5].type == 8 and t[i + 6].type == 4]
    cnt = t[q[0] - 1]
    assert cnt.type == 4 and cnt.value == len(q)
    gone = [i for i in q if t[i + 4].value in OLD and (rec(t[i + 2].value) or '').startswith('CheatDeath_')]
    out = bytearray(buf)
    for i in reversed(gone):
        del out[t[i].pos:t[i + 7].pos]
    struct.pack_into('<i', out, cnt.pos + 1, cnt.value - len(gone))
    d = -sum(t[i + 7].pos - t[i].pos for i in gone)
    bp, size = sv.block(buf, 'WHDC')
    struct.pack_into('<I', out, bp + 8, size + d)
    struct.pack_into('<I', out, bp + 16, size + d - 4)
    return bytes(sv.fix_lengths(out, d)), [t[i + 4].value for i in gone]


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    live_p, src_p, out_p = sys.argv[1:4]
    gd = GameData(os.path.join(ROOT, 'app', 'gui', 'data', 'game.gamedb'),
                  os.path.join(ROOT, 'app', 'gui', 'data', 'string_ruru.strdb'))
    rec = gd.record
    live, source = sv.load(live_p)[0], sv.load(src_p)[0]
    live, gone = drop_old(live, rec)
    print('Из очереди убраны ждущие засады опыта 61:', gone)
    have = {(o['name'], o['title']) for o in orcs.read(live, gd)}       # already in the save (experiment 61)
    picked = [o for o in orcs.recommend(orcs.read(source, gd), total=60)[20:] if (o['name'], o['title']) not in have]
    killed = [o for o in picked if o['dead'] and o['killer_name'] == 'Талион' and 'HeadRemoved' not in o['death_cause']
              and 'Dopple' not in o['role_key']]
    living = [o for o in picked if not (o['dead'] and o['killer_name'] == 'Талион')]
    pools = {'CheatDeath_Ambush': killed[:4], 'RoleTransformation_Ambush': living[:2]}
    roles, real_prepare, scars = {}, orc_ghosts.prepare, {}

    def prepare(raw, number, region, reward, rec_, day=1):
        out, src_region, days = real_prepare(raw, number, region, reward, rec_, day)
        role, level, follower, alive = roles[number]
        out = orc_ambush20.fix(out, rec_, role, level, follower, alive)
        if number in scars:                       # the looks of the return written in beforehand
            out, _ = returned.looks(out, scars[number], rec_)
        return out, src_region, days
    orc_ghosts.prepare = prepare
    p, t, mg, n, starts, end = orc_ghosts.orc_insert.table(live, rec)
    # orc_ghosts.build sets timer = first + k * step: here first 0, step 1 ms, the minutes added by rewriting
    spec, lines, timers = [], [], []
    for k, (minute, kind) in enumerate(PLAN):
        o = pools[kind].pop(0)
        rng = random.Random(returned.SEED * 100003 + o['number'])
        level = rng.randint(40, 50)
        if kind == 'RoleTransformation_Ambush':
            roles[n + k] = (None, level, False, True)
            spec.append((o['number'], '@' + kind))
            what = 'жив' if not o['dead'] else 'был убит орком'
        else:
            s = returned.scar(o['death_cause'], rng)
            scars[n + k] = s
            roles[n + k] = (returned.SCARS[s][0], level, False, False)
            spec.append((o['number'], returned.REWARDS.get(s, 'ResReward_PinnicleScar_' + s)))
            what = '%s → %s' % (o['death_cause'], returned.TITLES[s])
        timers.append(minute * 60000)
        lines.append('№%d через %2d мин  %-15s %s %s, ур. %d, %s' % (
            n + k, minute, {'CheatDeath_Ambush': 'обманул смерть', 'RoleTransformation_Ambush': 'орк изменился'}[kind],
            o['name'], o['title'], level, what))
    new = bytearray(orc_ghosts.build(live, source, spec, 'Faction_island', gd, log=lambda *a: None, first=0, step=1))
    t = sv.block_tokens(bytes(new), 'WHDC')
    for i in range(len(t) - 7):                   # the timers of the new events: k ms -> the planned minutes
        if t[i].type == 0x0C and t[i + 4].type == 4 and n <= t[i + 4].value < n + len(PLAN) and t[i + 6].type == 4 \
                and t[i + 2].type == 0 and (rec(t[i + 2].value) or '') in dict((b, a) for a, b in PLAN):
            struct.pack_into('<i', new, t[i + 6].pos + 1, timers[t[i + 4].value - n])
    new = bytes(new)
    sv.validate(new, 'результат')
    os.makedirs(os.path.dirname(os.path.abspath(out_p)), exist_ok=True)
    sv.write(out_p, new, crypto.user_id_from_name(out_p))
    assert sv.load(out_p)[1] == 0x096c2a9f
    for s in lines:
        print(s)
    print('Записано:', out_p)


if __name__ == '__main__':
    main()
