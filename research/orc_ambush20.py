"""Experiment 61: the twenty by ambushes, all three kinds at once in Nurn, none on the map (research).

    python research/orc_ambush20.py <base> <source> <out> [--first seconds] [--step seconds]

The orcs that troubled Talion most (orcs.recommend, 30 taken to have six living): the killed by Talion — the first
6 "cheated death" (CheatDeath_Ambush), the next 8 betrayals (CheatDeath_Betrayal, PlayerFollower forced: only a
follower can betray, experiments 39-41); 6 living or killed by orcs — "the orc changed" (RoleTransformation_Ambush).
The kinds take turns in the queue; timers first + k*step. The dead get the reward and the role of returned.scar
(the role in the record gives the origin line, experiment 9); all get a level 40-50 (seeded). Records are added at the
end of MainGame without a place (orc_ghosts.build: the game seats a comer itself).
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
import orc_ghosts                                           # noqa: E402

orc_ghosts.KEEP_FOLLOWER = True          # the follower bits are set below, orc by orc
KINDS = ['CheatDeath_Ambush', 'RoleTransformation_Ambush', 'CheatDeath_Betrayal']
COUNTS = {'CheatDeath_Ambush': 6, 'RoleTransformation_Ambush': 6, 'CheatDeath_Betrayal': 8}
FOLLOWER = 27


def order():
    """The kinds taking turns while each has some left: CD, RT, BT, CD, RT, BT, … then the rest of the betrayals."""
    left, out = dict(COUNTS), []
    while any(left.values()):
        for k in KINDS:
            if left[k]:
                out.append(k)
                left[k] -= 1
    return out


def fix(raw, rec, role, level, follower, alive):
    """Level (both copies), the role in every copy, the follower bit, the death flags off for a living one."""
    raw = bytearray(raw)
    t = sv.tokens(bytes(raw), 0, len(raw))
    d = orcs._desc_start(t, 0, len(t))
    struct.pack_into('<I', raw, t[d + 8].pos + 1, level - 1)
    struct.pack_into('<i', raw, t[d + 9].pos + 1, level - 1)
    if role:
        for r in t[d:]:
            if r.type == 0 and (rec(r.value) or '').startswith('Role_'):
                raw[r.pos + 1:r.pos + 5] = struct.pack('<I', name_hash(role))
    f = next(x for x in t[d:] if x.type == 0x05)
    bits = int.from_bytes(raw[f.pos + 1:f.pos + 9], 'little')
    for n in ('Dominated', 'PlayerFollower', 'Spy', 'PlayerBodyguard'):
        bits &= ~(1 << orcs.FLAGS.index(n))
    if follower:
        bits |= 1 << FOLLOWER
    if alive:
        for n in returned.OFF:
            bits &= ~(1 << orcs.FLAGS.index(n))
    raw[f.pos + 1:f.pos + 9] = bits.to_bytes(8, 'little')
    return bytes(raw)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    first = int(sys.argv[sys.argv.index('--first') + 1]) if '--first' in sys.argv else 360
    step = int(sys.argv[sys.argv.index('--step') + 1]) if '--step' in sys.argv else 90
    args = [a for a in args if a not in (str(first), str(step))]
    base_p, src_p, out_p = args[:3]
    gd = GameData(os.path.join(ROOT, 'app', 'gui', 'data', 'game.gamedb'),
                  os.path.join(ROOT, 'app', 'gui', 'data', 'string_ruru.strdb'))
    rec = gd.record
    base, source = sv.load(base_p)[0], sv.load(src_p)[0]
    picked = orcs.recommend(orcs.read(source, gd), total=30)
    killed = [o for o in picked if o['dead'] and o['killer_name'] == 'Талион']
    living = [o for o in picked if not (o['dead'] and o['killer_name'] == 'Талион')]
    pools = {'CheatDeath_Ambush': killed[:6], 'CheatDeath_Betrayal': killed[6:14],
             'RoleTransformation_Ambush': living[:6]}
    assert all(len(pools[k]) == COUNTS[k] for k in KINDS), {k: len(v) for k, v in pools.items()}
    plan = []                                    # [(orc, kind)]
    for kind in order():
        plan.append((pools[kind].pop(0), kind))
    # orc_ghosts.build takes (number, reward or '@ambush'); its prepare is wrapped to add level, role, follower
    roles, real_prepare = {}, orc_ghosts.prepare

    def prepare(raw, number, region, reward, rec_, day=1):
        out, src_region, days = real_prepare(raw, number, region, reward, rec_, day)
        role, level, follower, alive = roles[number]
        return fix(out, rec_, role, level, follower, alive), src_region, days
    orc_ghosts.prepare = prepare
    p, t, mg, n, starts, end = orc_ghosts.orc_insert.table(base, rec)
    spec, lines = [], []
    for k, (o, kind) in enumerate(plan):
        rng = random.Random(returned.SEED * 100003 + o['number'])
        level = rng.randint(40, 50)
        if kind == 'RoleTransformation_Ambush':
            roles[n + k] = (None, level, False, True)
            spec.append((o['number'], '@' + kind))
            what = 'жив' if not o['dead'] else 'был убит орком'
        else:
            names = set()
            s = returned.scar(o['death_cause'], rng, False, False)
            role = returned.SCARS[s][0]
            reward = returned.REWARDS.get(s, 'ResReward_PinnicleScar_' + s)
            roles[n + k] = (role, level, kind == 'CheatDeath_Betrayal', False)
            spec.append((o['number'], reward + ('@' + kind if kind != 'CheatDeath_Ambush' else '')))
            what = '%s, %s' % (o['death_cause'] or '?', returned.TITLES[s])
        lines.append('%2d. через %4d с (%2d:%02d) %-26s %-10s %-24s ур. %d, %s'
                     % (k + 1, first + k * step, (first + k * step) // 60, (first + k * step) % 60,
                        {'CheatDeath_Ambush': 'обманул смерть', 'CheatDeath_Betrayal': 'предательство',
                         'RoleTransformation_Ambush': 'орк изменился'}[kind], o['name'], o['title'], level, what))
    new = orc_ghosts.build(base, source, spec, 'Faction_island', gd, log=lambda *a: None, first=first * 1000,
                           step=step * 1000)
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
