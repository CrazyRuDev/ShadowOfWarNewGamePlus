"""Experiment: copy one orc from a source save to the end of the base's MainGame orc table (research).

    python research/orc_insert.py <base> <source> <orc number in source> <out> [--region Faction_island] [--pool]

The orc gets the next number of the base (= its place in the table), the table header grows by 1. The registry
after the table is not touched (experiment 1). Optionally the orc is moved to another region.
"""
import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app', 'engine'))
from sowtool import save as sv                        # noqa: E402
from sowtool.gamedata import GameData, name_hash      # noqa: E402

MAIN = name_hash('MainGame')
BG = name_hash('BG')


def table(buf, rec):
    """(WHDC tokens, MainGame header token index, [record start token indexes], end token index of the table)."""
    p, size = sv.block(buf, 'WHDC')
    t = sv.tokens(buf, p + 20, p + 16 + size)
    mg = next(i for i in range(len(t)) if t[i].type == 0 and t[i].value == MAIN and t[i + 1].type == 0x0C)
    n = t[mg + 2].value
    starts = [j - 1 for j in range(mg + 3, len(t) - 3) if t[j - 1].type == 0x0C and t[j - 1].value == 1
              and t[j].type == 4 and t[j + 1].type == 9 and t[j + 2].type == 8 and t[j + 3].type == 0
              and re.match(r'(Invasion)?Faction_', rec(t[j + 3].value) or '')]
    # the table ends where the registry starts: the run of 04 numbers right before the world places list (00 BG)
    bg = next(i for i in range(starts[-1], len(t)) if t[i].type == 0 and t[i].value == BG)
    end = bg
    while t[end - 1].type == 4:
        end -= 1
    return p, t, mg, n, starts, end


def record(buf, rec, number):
    """Bytes of an orc's MainGame record and its tokens."""
    p, t, mg, n, starts, end = table(buf, rec)
    k = next(i for i, s in enumerate(starts) if t[s + 1].value == number)
    a = t[starts[k]].pos
    b = t[starts[k + 1]].pos if k + 1 < len(starts) else t[end].pos
    return buf[a:b]


def insert(base, source, number, gd, region=None, log=print, pool=False):
    rec = gd.record
    raw = bytearray(record(source, rec, number))
    p, t, mg, n, starts, end = table(base, rec)
    # its number (04 at offset 2: 0c 01 | 04 <number>) becomes the base's next one
    assert raw[0:2] == b'\x0c\x01' and raw[2] == 4
    old = struct.unpack_from('<i', raw, 3)[0]
    struct.pack_into('<i', raw, 3, n)
    if region:
        src_region = None
        rt = sv.tokens(bytes(raw), 0, len(raw))
        for x in rt:
            if x.type == 0 and re.match(r'Faction_', rec(x.value) or ''):
                src_region = rec(x.value)
                break
        a, b = struct.pack('<I', name_hash(src_region)), struct.pack('<I', name_hash(region))
        count = 0
        for x in rt:                                  # every 00 <old region> token of the record
            if x.type == 0 and x.value == name_hash(src_region):
                raw[x.pos + 1:x.pos + 5] = b
                count += 1
        log('регион %s -> %s (%d мест)' % (src_region, region, count))
    npc = re.search(rb'[0-9a-f]{32}_NPC_\d+', bytes(raw))
    if npc and base.find(npc.group()) >= 0:
        raise SystemExit('строка %s уже есть в опоре' % npc.group().decode())
    at = t[end].pos
    add = b''
    if pool:
        # the registry right after the table starts with 04 <count> and the numbers of the orcs without a hierarchy
        # place (the game appends a new place-less orc there); the orc goes to its end
        count = t[end].value
        last = t[end + count]
        add_at = last.end
        add = b'\x04' + struct.pack('<i', n)
        out = bytearray(base[:at] + bytes(raw) + base[at:add_at] + add + base[add_at:])
        struct.pack_into('<i', out, t[end].pos + len(raw) + 1, count + 1)
        log('реестр: первый список %d -> %d (номер %d в конце)' % (count, count + 1, n))
    else:
        out = bytearray(base[:at] + bytes(raw) + base[at:])
    struct.pack_into('<i', out, t[mg + 2].pos + 1, n + 1)        # MainGame header: one record more
    # WHDC block lengths (both fields), then the section and file lengths
    d = len(raw) + len(add)
    bp, size = sv.block(base, 'WHDC')
    struct.pack_into('<I', out, bp + 8, size + d)
    struct.pack_into('<I', out, bp + 16, size + d - 4)
    out = sv.fix_lengths(out, d)
    log('орк №%d источника -> №%d опоры, %d байт; MainGame %d -> %d' % (old, n, d, n, n + 1))
    return out


def pool_add(buf, number, gd, log=print):
    """An orc already in the base's MainGame table written to the end of the registry's first list (orcs without
    a hierarchy place), the list length +1."""
    p, t, mg, n, starts, end = table(buf, gd.record)
    count = t[end].value
    lst = [x.value for x in t[end + 1:end + 1 + count]]
    if number in lst:
        raise SystemExit('№%d уже в реестре' % number)
    if not 0 <= number < n:
        raise SystemExit('№%d нет в таблице (в ней %d)' % (number, n))
    at = t[end + count].end
    out = bytearray(buf[:at] + b'\x04' + struct.pack('<i', number) + buf[at:])
    struct.pack_into('<i', out, t[end].pos + 1, count + 1)
    bp, size = sv.block(buf, 'WHDC')
    struct.pack_into('<I', out, bp + 8, size + 5)
    struct.pack_into('<I', out, bp + 16, size + 1)
    log('реестр: первый список %d -> %d (номер %d в конце)' % (count, count + 1, number))
    return sv.fix_lengths(out, 5)


if __name__ == '__main__' and sys.argv[1:2] == ['pool']:
    # python research/orc_insert.py pool <save> <number> <out>
    sys.stdout.reconfigure(encoding='utf-8')
    gd = GameData(os.path.join(ROOT, 'app', 'gui', 'data', 'game.gamedb'),
                  os.path.join(ROOT, 'app', 'gui', 'data', 'string_ruru.strdb'))
    buf, user = sv.load(sys.argv[2])
    new = pool_add(buf, int(sys.argv[3]), gd)
    sv.validate(new, 'результат')
    from sowtool import crypto
    sv.write(sys.argv[4], new, crypto.user_id_from_name(sys.argv[4]))
    print('Записано:', sys.argv[4])
    sys.exit(0)

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    base_p, src_p, num, out_p = sys.argv[1:5]
    region = sys.argv[sys.argv.index('--region') + 1] if '--region' in sys.argv else None
    gd = GameData(os.path.join(ROOT, 'app', 'gui', 'data', 'game.gamedb'),
                  os.path.join(ROOT, 'app', 'gui', 'data', 'string_ruru.strdb'))
    base, user = sv.load(base_p)
    source, _ = sv.load(src_p)
    new = insert(base, source, int(num), gd, region, pool='--pool' in sys.argv)
    sv.validate(new, 'результат')
    sv.write(out_p, new, user if '_ShadowOfWar' not in os.path.basename(out_p) else
             __import__('sowtool.crypto', fromlist=['x']).user_id_from_name(out_p))
    print('Записано:', out_p)
