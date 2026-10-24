"""Experiment: dead orcs of the source come back in the base through "cheated death" ambushes (research).

    python research/orc_ghosts.py <base> <source> <out> <number>:<ResReward_*> [...] [--region Faction_island]
        [--first seconds] [--step seconds]

Each orc: its source record goes to the end of the base's MainGame table (next numbers, header grows), region
changed, every history day = 1, flags IsDead + CanResurrect + PresentedToPlayer + IdentityPresented, one
resurrection reward (00 ResReward_* in the reward list at the record end), no hierarchy place. Then one
CheatDeath_Ambush per orc in the Nemesis event queue (0c 01 | 00 Faction | 00 CheatDeath_Ambush | 00 Faction |
04 orc | 08 tag | 04 timer ms), the queue counter grows.
"""
import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app', 'engine'))
sys.path.insert(0, os.path.join(ROOT, 'research'))
from sowtool import crypto, save as sv                # noqa: E402
from sowtool.gamedata import GameData, name_hash      # noqa: E402
import orc_insert                                     # noqa: E402

FLAGS = (2, 4, 5, 7, 9)       # IsDead, CanResurrect, PresentedToPlayer, IdentityPresented, HasEverSpawned
ALIVE_FLAGS = (5, 7, 9)
FOLLOWER_FLAGS = (8, 27, 28, 29)   # Dominated, PlayerFollower, Spy, PlayerBodyguard (orcs.FLAGS)
# --keep-follower: the betrayal ambushes need a follower (every real betrayal in the saves: the event, then the game's
# own IsPlayerFollowerRemove); experiment 39 cleared the flags and the betrayals never came
KEEP_FOLLOWER = '--keep-follower' in sys.argv       # a living one: without HasEverSpawned a place-less orc is deleted on load
FIRST_TIMER, STEP = 30000, 90000


def current_day(buf, rec):
    """The base's current day: the latest day in its orcs' histories (0 at the start of a new game)."""
    import orc_days
    p, t, mg, n, starts, end = orc_insert.table(buf, rec)
    days = [t[i].value for s in starts for i in orc_days.history(t, starts, end, t[s + 1].value, rec)]
    return max(days) if days else 0


def history_day(base, rec):
    """The day transferred histories get: current day - 5, not below 0 (never after the current day)."""
    cur = current_day(base, rec)
    return max(0, min(cur, cur - 5))


def prepare(raw, number, region, reward, rec, day=1):
    """The record bytes with the new number, region, days, flags and reward (reward None: a living orc, only
    PresentedToPlayer + IdentityPresented are set)."""
    raw = bytearray(raw)
    struct.pack_into('<i', raw, 3, number)
    t = sv.tokens(bytes(raw), 0, len(raw))
    src_region = next(rec(x.value) for x in t if x.type == 0 and (rec(x.value) or '').startswith('Faction_'))
    for x in t:
        if x.type == 0 and x.value == name_hash(src_region):
            raw[x.pos + 1:x.pos + 5] = struct.pack('<I', name_hash(region))
    # 0c 01 | 04 n | 09 | 08 name | 00 faction | 00 faction | 00 AI | 00 place: no place (the pool), whatever it was
    assert t[7].type == 0
    raw[t[7].pos + 1:t[7].pos + 5] = b'\0\0\0\0'
    # the history: the longest unbroken run of '00 <event> 03 <day>' pairs (the death record further on is left)
    pair = [t[i].type == 0 and t[i].value and rec(t[i].value) and t[i + 1].type == 3 for i in range(len(t) - 1)]
    best, i = (0, 0), 0
    while i < len(pair):
        j = i
        while j < len(pair) and pair[j]:
            j += 2
        if (j - i) // 2 > best[1]:
            best = (i, (j - i) // 2)
        i = j + 1 if j == i else j
    days = best[1]
    for k in range(days):
        struct.pack_into('<h', raw, t[best[0] + 2 * k + 1].pos + 1, day)
    from sowtool import orcs                   # an orc never put into the world has an empty _NPC_ id
    f = next(x for x in t[orcs._desc_start(t, 0, len(t)):] if x.type == 0x05)
    flags = int.from_bytes(raw[f.pos + 1:f.pos + 9], 'little')
    for bit in (FLAGS if reward else ALIVE_FLAGS):
        flags |= 1 << bit
    if not KEEP_FOLLOWER:                      # a former follower of Talion comes back as an enemy
        for bit in FOLLOWER_FLAGS:
            flags &= ~(1 << bit)
    raw[f.pos + 1:f.pos + 9] = flags.to_bytes(8, 'little')
    if not reward:
        return bytes(raw), src_region, days
    # a death record for an orc alive in the source: cause empty -> killed by Talion's blade (as orc_deathfix --player)
    tlo = next(i for i, x in enumerate(t) if x.type == 0 and (rec(x.value) or '').startswith('TraitLevelOffset_'))
    d = next(i for i in range(tlo, len(t) - 6) if t[i].type == 0 and t[i + 1].type == 3 and t[i + 2].type == 3
             and t[i + 3].type == 4 and t[i + 4].type == 0 and t[i + 5].type == 0)
    if not t[d].value:
        raw[t[d].pos + 1:t[d].pos + 5] = struct.pack('<I', name_hash('Resurrection_PlayerSlash'))
        raw[t[d + 3].pos + 1:t[d + 3].pos + 5] = struct.pack('<i', -1)
        raw[t[d + 4].pos + 1:t[d + 4].pos + 5] = struct.pack('<I', name_hash('Player_Character'))
        raw[t[d + 5].pos + 1:t[d + 5].pos + 5] = struct.pack('<I', name_hash('PC_Bip_LastWordsKill_CombatFinish'))
    # record end: ... 04 <rewards> (00 ResReward_*)*n | 04 x | 00 0 | 02 n | 00 <role or 0>
    tail = t[-5:]
    assert [x.type for x in tail] == [4, 4, 0, 2, 0], [x.type for x in tail]
    n_tok = tail[0]
    assert n_tok.value == 0, 'награды уже есть'
    raw[n_tok.pos + 1:n_tok.pos + 5] = struct.pack('<i', 1)
    raw = raw[:n_tok.end] + b'\x00' + struct.pack('<I', name_hash(reward)) + raw[n_tok.end:]
    return bytes(raw), src_region, days


def build(base, source, orcs, region, gd, log=print, first=FIRST_TIMER, step=STEP):
    """orcs: [(source number, ResReward_* for a dead one | '@<ambush>' for a living one)]"""
    rec = gd.record
    p, t, mg, n, starts, end = orc_insert.table(base, rec)
    day = history_day(base, rec)
    log('текущий день опоры %d -> дни истории %d' % (current_day(base, rec), day))
    records, events = [], []
    for k, (num, reward) in enumerate(orcs):
        new_num = n + k
        # '<ResReward_*>' — dead, CheatDeath_Ambush; '@<ambush>' — alive; '<ResReward_*>@<ambush>' — dead, that
        # ambush (CheatDeath_Betrayal: a dead follower comes back a traitor, experiment 41)
        if reward.startswith('@'):
            ambush, reward = reward[1:], None
        elif '@' in reward:
            reward, ambush = reward.split('@')
        else:
            ambush = 'CheatDeath_Ambush'
        raw, src_region, days = prepare(orc_insert.record(source, rec, num), new_num, region, reward, rec, day)
        records.append(raw)
        timer = first + k * step
        events.append(b'\x0c\x01' + b'\x00' + struct.pack('<I', name_hash(region)) + b'\x00' +
                      struct.pack('<I', name_hash(ambush)) + b'\x00' + struct.pack('<I', name_hash(region)) +
                      b'\x04' + struct.pack('<i', new_num) + b'\x08' + struct.pack('<I', 0) + b'\x04' +
                      struct.pack('<i', timer))
        log('№%d -> №%d, %s -> %s, событий истории %d, %s, засада %s через %d с игры'
            % (num, new_num, src_region, region, days, ('мёртв, награда ' + reward) if reward else 'живой', ambush,
               timer // 1000))
    # the event queue: 04 <count> right before its first entry
    q = [i for i in range(len(t) - 7) if t[i].type == 0x0C and t[i].value == 1 and t[i + 1].type == 0
         and (rec(t[i + 1].value) or '').startswith('Faction_') and t[i + 2].type == 0 and t[i + 3].type == 0
         and t[i + 4].type == 4 and t[i + 5].type == 8 and t[i + 6].type == 4]
    cnt = t[q[0] - 1]
    assert cnt.type == 4 and cnt.value == len(q), (cnt.value, len(q))
    add_r, add_e = b''.join(records), b''.join(events)
    at_r, at_e = t[end].pos, t[q[0]].pos
    assert at_r < at_e
    out = bytearray(base[:at_r] + add_r + base[at_r:at_e] + add_e + base[at_e:])
    struct.pack_into('<i', out, t[mg + 2].pos + 1, n + len(orcs))
    struct.pack_into('<i', out, cnt.pos + len(add_r) + 1, cnt.value + len(orcs))
    d = len(add_r) + len(add_e)
    bp, size = sv.block(base, 'WHDC')
    struct.pack_into('<I', out, bp + 8, size + d)
    struct.pack_into('<I', out, bp + 16, size + d - 4)
    log('MainGame %d -> %d, очередь событий %d -> %d' % (n, n + len(orcs), cnt.value, cnt.value + len(orcs)))
    return sv.fix_lengths(out, d)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    args = [a for a in sys.argv[1:] if not a.startswith('--')]  # --keep-follower: see KEEP_FOLLOWER
    region = sys.argv[sys.argv.index('--region') + 1] if '--region' in sys.argv else 'Faction_island'
    first = int(sys.argv[sys.argv.index('--first') + 1]) * 1000 if '--first' in sys.argv else FIRST_TIMER
    step = int(sys.argv[sys.argv.index('--step') + 1]) * 1000 if '--step' in sys.argv else STEP
    opts = {region} | {sys.argv[sys.argv.index(o) + 1] for o in ('--first', '--step') if o in sys.argv}
    args = [a for a in args if a not in opts]
    base_p, src_p, out_p = args[:3]
    orcs = [(int(a.split(':')[0]), a.split(':')[1]) for a in args[3:]]
    gd = GameData(os.path.join(ROOT, 'app', 'gui', 'data', 'game.gamedb'),
                  os.path.join(ROOT, 'app', 'gui', 'data', 'string_ruru.strdb'))
    base, _ = sv.load(base_p)
    source, _ = sv.load(src_p)
    new = build(base, source, orcs, region, gd, first=first, step=step)
    sv.validate(new, 'результат')
    sv.write(out_p, new, crypto.user_id_from_name(out_p))
    print('Записано:', out_p)
