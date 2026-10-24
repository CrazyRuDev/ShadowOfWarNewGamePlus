"""Experiment: blood brothers — a living orc of the pool tied to a living captain (research).

    python research/orc_bond.py <save>                                                    (show the relations)
    python research/orc_bond.py <base> <source> <out> <captain>:<brother> [...] [--type BloodBrother_SpawnIn]

<brother>: a number in the base, or s<number> — a living orc of the source copied to the end of the base's table
(next numbers, no place, PresentedToPlayer + IdentityPresented + HasEverSpawned, history days as orc_ghosts).
The relation goes into BOTH records: the list right after the death record, at TraitLevelOffset_* + 15:
04 <count> | (0c 01 | 00 <type> | 00 Faction | 04 <orc> | 00 Faction | 04 <orc>)*count.
"""
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app', 'engine'))
sys.path.insert(0, os.path.join(ROOT, 'research'))
from sowtool import crypto, save as sv                # noqa: E402
from sowtool.gamedata import GameData, name_hash      # noqa: E402
import orc_ghosts                                     # noqa: E402
import orc_insert                                     # noqa: E402


def ranges(buf, rec):
    """{orc number: (start byte, end byte)} of the MainGame records."""
    p, t, mg, n, starts, end = orc_insert.table(buf, rec)
    out = {}
    for k, s in enumerate(starts):
        out[t[s + 1].value] = (t[s].pos, t[starts[k + 1]].pos if k + 1 < len(starts) else t[end].pos)
    return out


def relations(raw, rec):
    """(token of the relation count, [(type, faction a, a, faction b, b)]) of one record."""
    t = sv.tokens(raw, 0, len(raw))
    tlo = next(i for i, x in enumerate(t) if x.type == 0 and (rec(x.value) or '').startswith('TraitLevelOffset_'))
    c = t[tlo + 15]
    assert c.type == 4, ('TLO+15', c)
    rels = []
    for k in range(c.value):
        r = t[tlo + 16 + 6 * k: tlo + 22 + 6 * k]
        assert r[0].type == 0x0C and r[1].type == 0 and r[3].type == 4 and r[5].type == 4, r
        rels.append((rec(r[1].value), rec(r[2].value), r[3].value, rec(r[4].value), r[5].value))
    return c, rels


def add_relation(raw, rec, kind, fa, a, fb, b):
    c, _ = relations(raw, rec)
    raw = bytearray(raw)
    struct.pack_into('<i', raw, c.pos + 1, c.value + 1)
    entry = (b'\x0c\x01' + b'\x00' + struct.pack('<I', name_hash(kind)) + b'\x00' + struct.pack('<I', name_hash(fa)) +
             b'\x04' + struct.pack('<i', a) + b'\x00' + struct.pack('<I', name_hash(fb)) + b'\x04' + struct.pack('<i', b))
    return bytes(raw[:c.end] + entry + raw[c.end:])


def region_of(raw, rec):
    t = sv.tokens(raw, 0, len(raw))
    return rec(t[4].value)


def splice(buf, changes):
    """changes: [(start, end, new bytes)] inside WHDC; lengths fixed."""
    out = bytearray(buf)
    d = 0
    for a, b, new in sorted(changes, reverse=True):
        out[a:b] = new
        d += len(new) - (b - a)
    bp, size = sv.block(buf, 'WHDC')
    struct.pack_into('<I', out, bp + 8, size + d)
    struct.pack_into('<I', out, bp + 16, size + d - 4)
    return sv.fix_lengths(out, d)


def add_pool(base, source, nums, region, gd, log=print):
    """Copy living source orcs to the end of the table; returns (save, [new numbers])."""
    rec = gd.record
    p, t, mg, n, starts, end = orc_insert.table(base, rec)
    day = orc_ghosts.history_day(base, rec)
    raws, new = [], []
    for k, num in enumerate(nums):
        raw, src_region, days = orc_ghosts.prepare(orc_insert.record(source, rec, num), n + k, region, None, rec, day)
        raws.append(raw)
        new.append(n + k)
        log('из источника №%d -> №%d (%s -> %s, дни истории %d)' % (num, n + k, src_region, region, day))
    out = bytearray(base)
    struct.pack_into('<i', out, t[mg + 2].pos + 1, n + len(nums))
    at = t[end].pos
    return splice(bytes(out), [(at, at, b''.join(raws))]), new


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    gd = GameData(os.path.join(ROOT, 'app', 'gui', 'data', 'game.gamedb'),
                  os.path.join(ROOT, 'app', 'gui', 'data', 'string_ruru.strdb'))
    rec = gd.record
    if len(sys.argv) == 2:
        buf, _ = sv.load(sys.argv[1])
        for num, (a, b) in sorted(ranges(buf, rec).items()):
            try:
                _, rels = relations(buf[a:b], rec)
            except (StopIteration, AssertionError):
                continue
            for r in rels:
                print('№%-4d %s %s:%d / %s:%d' % ((num,) + r))
        sys.exit(0)
    kind = sys.argv[sys.argv.index('--type') + 1] if '--type' in sys.argv else 'BloodBrother_SpawnIn'
    args = [a for a in sys.argv[1:] if not a.startswith('--') and a != kind]
    base_p, src_p, out_p = args[:3]
    pairs = [a.split(':') for a in args[3:]]
    buf, _ = sv.load(base_p)
    source, _ = sv.load(src_p)
    region = region_of(buf[slice(*ranges(buf, rec)[int(pairs[0][0])])], rec)
    copy = [int(b[1:]) for _, b in pairs if b.startswith('s')]
    buf, new = add_pool(buf, source, copy, region, gd)
    it = iter(new)
    pairs = [(int(c), next(it) if b.startswith('s') else int(b)) for c, b in pairs]
    rg = ranges(buf, rec)
    raws = {}
    for c, b in pairs:
        for x in (c, b):
            raws.setdefault(x, buf[slice(*rg[x])])
        rc, rb = region_of(raws[c], rec), region_of(raws[b], rec)
        for x in (c, b):
            raws[x] = add_relation(raws[x], rec, kind, rc, c, rb, b)
        print('%s: капитан №%d (%s) <-> брат №%d (%s)' % (kind, c, rc, b, rb))
    buf = splice(buf, [rg[x] + (raw,) for x, raw in raws.items()])
    sv.validate(buf, 'результат')
    for x in raws:
        print('№%d связи: %s' % (x, relations(buf[slice(*ranges(buf, rec)[x])], rec)[1]))
    sv.write(out_p, buf, crypto.user_id_from_name(out_p))
    print('Записано:', out_p)
