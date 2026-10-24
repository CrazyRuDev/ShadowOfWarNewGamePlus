"""Experiment 50: "came back beforehand" — an orc killed by Talion in the finished game stands on the map from the start,
already returned from the dead (no ambush), to see whether it tells its story at the first meeting.

    python research/orc_returned.py <base> <source> <source orc number> <ResReward_*> <Role_*> <level> <out>

The record takes the cell of a Nurn captain the game has not put into the world yet (army._prepare: number, region,
place, history days, relations, flags of having been seen), then: level, flags IsDead/CanResurrect off and
IsResurrected/HasEverSpawned on, the role (with an origin line in the orc's voice) and the reward list = that reward.
The death record (cause, killer Talion) stays — after a real return the game keeps it too (Tkhrak, experiment 41).
"""
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app', 'engine'))
from sowtool import army, crypto, ngplus, orcs, save as sv   # noqa: E402
from sowtool.gamedata import GameData, name_hash               # noqa: E402

ON, OFF = ('IsResurrected', 'HasEverSpawned'), ('IsDead', 'CanResurrect', 'KilledByPlayer', 'IsDeadMockMember')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    base_p, src_p, num, reward, role, level, out_p = sys.argv[1:8]
    num, level = int(num), int(level)
    gd = GameData(os.path.join(ROOT, 'app', 'gui', 'data', 'game.gamedb'),
                  os.path.join(ROOT, 'app', 'gui', 'data', 'string_ruru.strdb'))
    rec = gd.record
    assert rec(name_hash(reward)) == reward and rec(name_hash(role)) == role
    base, source = sv.load(base_p)[0], sv.load(src_p)[0]
    targets, _ = army._targets(base, gd)
    row, old = next((r, o) for r, o in targets['island'] if r.startswith('island_Row_Captain'))
    sa, sb = army._record(source, *army._table(source, rec), num)
    raw = bytearray(army._prepare(source[sa:sb], old['number'], 'Faction_island', row, level,
                                  max(0, ngplus.base_day(base) - 5), rec))
    t = sv.tokens(bytes(raw), 0, len(raw))
    d = orcs._desc_start(t, 0, len(t))
    f = next(x for x in t[d:] if x.type == 0x05)
    bits = int.from_bytes(raw[f.pos + 1:f.pos + 9], 'little')
    for n in OFF:
        bits &= ~(1 << orcs.FLAGS.index(n))
    for n in ON:
        bits |= 1 << orcs.FLAGS.index(n)
    raw[f.pos + 1:f.pos + 9] = bits.to_bytes(8, 'little')
    r = next(x for x in t[d:] if x.type == 0 and (rec(x.value) or '').startswith('Role_'))
    raw[r.pos + 1:r.pos + 5] = struct.pack('<I', name_hash(role))
    # rewards at the record end: 04 <n> (00 ResReward_*)*n | 04 | 00 | 02 | 00
    tail = t[-5:]
    assert [x.type for x in tail] == [4, 4, 0, 2, 0], [x.type for x in tail]
    k = len(t) - 5                       # as orc_ghosts.prepare: an orc of the source has no rewards yet
    assert t[k].value == 0, 'награды уже есть'
    raw = raw[:t[k].pos] + b'\x04' + struct.pack('<i', 1) + b'\x00' + struct.pack('<I', name_hash(reward)) + \
        raw[t[len(t) - 4].pos:]
    t2, starts, end = army._table(base, rec)
    a, b = army._record(base, t2, starts, end, old['number'])
    bp, size = sv.block(base, 'WHDC')
    dd = len(raw) - (b - a)
    out = bytearray(base[:a] + bytes(raw) + base[b:])
    struct.pack_into('<I', out, bp + 8, size + dd)
    struct.pack_into('<I', out, bp + 16, size + dd - 4)
    out = bytes(sv.fix_lengths(out, dd))
    sv.validate(out, 'результат')
    os.makedirs(os.path.dirname(os.path.abspath(out_p)), exist_ok=True)
    sv.write(out_p, out, crypto.user_id_from_name(out_p))
    assert sv.load(out_p)[1] == 0x096c2a9f
    x = {o['number']: o for o in orcs.read(out, gd)}[old['number']]
    print('%s %s (источник №%d) — %s вместо №%d %s, ур. %d, %s, роль %s, награды %s, гибель: %s от %s; флаги %s'
          % (x['name'], x['title'], num, row, old['number'], old['name'], x['level'], x['personality'],
             x['role_key'], x['rewards'], x['death_cause'], x['killer_name'], x['flags']))
    print('Записано:', out_p)


if __name__ == '__main__':
    main()
