"""Experiment: add a Nemesis queue event for an orc already in the save (research).

    python research/orc_event.py <save> <out> <orc number> <event> [--timer seconds] [--region Faction_island]

Entry: 0c 01 | 00 Faction_<region> | 00 <event> | 00 Faction_<region> | 04 <orc> | 08 0 | 04 <ms>; the queue counter
(04 right before the first entry) grows by one.
"""
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app', 'engine'))
from sowtool import crypto, save as sv                # noqa: E402
from sowtool.gamedata import GameData, name_hash      # noqa: E402


def add_event(buf, rec, orc, event, region, timer_ms):
    p, size = sv.block(buf, 'WHDC')
    t = sv.tokens(buf, p + 20, p + 16 + size)
    q = [i for i in range(len(t) - 7) if t[i].type == 0x0C and t[i].value == 1 and t[i + 1].type == 0
         and (rec(t[i + 1].value) or '').startswith('Faction_') and t[i + 2].type == 0 and t[i + 3].type == 0
         and t[i + 4].type == 4 and t[i + 5].type == 8 and t[i + 6].type == 4]
    c = t[q[0] - 1]
    assert c.type == 4 and c.value == len(q)
    entry = (b'\x0c\x01' + b'\x00' + struct.pack('<I', name_hash(region)) + b'\x00' + struct.pack('<I', name_hash(event))
             + b'\x00' + struct.pack('<I', name_hash(region)) + b'\x04' + struct.pack('<i', orc) + b'\x08'
             + struct.pack('<I', 0) + b'\x04' + struct.pack('<i', timer_ms))
    at = t[q[0]].pos
    out = bytearray(buf[:at] + entry + buf[at:])
    struct.pack_into('<i', out, c.pos + 1, c.value + 1)
    struct.pack_into('<I', out, p + 8, size + len(entry))
    struct.pack_into('<I', out, p + 16, size + len(entry) - 4)
    return sv.fix_lengths(out, len(entry))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    path, out_p, orc, event = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
    timer = int(sys.argv[sys.argv.index('--timer') + 1]) if '--timer' in sys.argv else 30
    region = sys.argv[sys.argv.index('--region') + 1] if '--region' in sys.argv else 'Faction_island'
    gd = GameData(os.path.join(ROOT, 'app', 'gui', 'data', 'game.gamedb'),
                  os.path.join(ROOT, 'app', 'gui', 'data', 'string_ruru.strdb'))
    buf, _ = sv.load(path)
    new = add_event(buf, gd.record, orc, event, region, timer * 1000)
    sv.validate(new, 'результат')
    sv.write(out_p, new, crypto.user_id_from_name(out_p))
    print('№%d: %s в %s через %d с игры. Записано: %s' % (orc, event, region, timer, out_p))
