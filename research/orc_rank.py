"""Experiment: set the two last values of an orc's record — 02 <rank?> | 00 <role in the settlement: Captain, ...>
(research). Same size, in place.

    python research/orc_rank.py <save> <out> <orc number> <rank> <Captain|0>
"""
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app', 'engine'))
sys.path.insert(0, os.path.join(ROOT, 'research'))
from sowtool import crypto, save as sv                # noqa: E402
from sowtool.gamedata import GameData, name_hash      # noqa: E402
import orc_insert                                     # noqa: E402

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    path, out_p, num, rank, role = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
    gd = GameData(os.path.join(ROOT, 'app', 'gui', 'data', 'game.gamedb'),
                  os.path.join(ROOT, 'app', 'gui', 'data', 'string_ruru.strdb'))
    rec = gd.record
    buf, _ = sv.load(path)
    p, t, mg, n, starts, end = orc_insert.table(buf, rec)
    k = next(i for i, s in enumerate(starts) if t[s + 1].value == num)
    e = starts[k + 1] if k + 1 < len(starts) else end
    j = e - 1
    while t[j].type == 0x0C and t[j].value == 0:      # empty table cells before the next record
        j -= 1
    r, q = t[j - 1], t[j]
    assert r.type == 2 and q.type == 0, (r, q)
    print('№%d: было 02 %d | %s -> 02 %d | %s' % (num, r.value, rec(q.value) or q.value, rank, role))
    out = bytearray(buf)
    out[r.pos + 1] = rank
    struct.pack_into('<I', out, q.pos + 1, 0 if role == '0' else name_hash(role))
    out = bytes(out)
    sv.validate(out, 'результат')
    sv.write(out_p, out, crypto.user_id_from_name(out_p))
    print('Записано:', out_p)
