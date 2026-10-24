"""Experiment: set or clear an orc's flags (research).

    python research/orc_flags.py <save> <out> <orc number> +RevengeTarget [-IsNew ...]

The flags are the first 05 (u64) token of the orc's description (after the _NPC_ string); names as in
research/orcs2.py FLAGS. Same size, in place.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app', 'engine'))
sys.path.insert(0, os.path.join(ROOT, 'research'))
from sowtool import crypto, save as sv                # noqa: E402
from sowtool.gamedata import GameData                 # noqa: E402
import orc_insert                                     # noqa: E402
import orcs2                                          # noqa: E402

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    path, out_p, num = sys.argv[1], sys.argv[2], int(sys.argv[3])
    gd = GameData(os.path.join(ROOT, 'app', 'gui', 'data', 'game.gamedb'),
                  os.path.join(ROOT, 'app', 'gui', 'data', 'string_ruru.strdb'))
    buf, _ = sv.load(path)
    p, t, mg, n, starts, end = orc_insert.table(buf, gd.record)
    k = next(i for i, s in enumerate(starts) if t[s + 1].value == num)
    e = starts[k + 1] if k + 1 < len(starts) else end
    npc = next(i for i in range(starts[k], e) if t[i].type == 0x0F and '_NPC_' in t[i].value)
    f = next(t[i] for i in range(npc, e) if t[i].type == 0x05)
    flags = int.from_bytes(buf[f.pos + 1:f.pos + 9], 'little')
    for a in sys.argv[4:]:
        bit = orcs2.FLAGS.index(a[1:])
        flags = flags | (1 << bit) if a[0] == '+' else flags & ~(1 << bit)
    out = bytearray(buf)
    out[f.pos + 1:f.pos + 9] = flags.to_bytes(8, 'little')
    out = bytes(out)
    print('№%d флаги: %s' % (num, ','.join(orcs2.FLAGS[b] for b in range(len(orcs2.FLAGS)) if flags >> b & 1)))
    sv.validate(out, 'результат')
    sv.write(out_p, out, crypto.user_id_from_name(out_p))
    print('Записано:', out_p)
