"""Experiment: set the day of every event in an orc's history (00 <event> 03 <day>) to one day (research).

    python research/orc_days.py <save> <orc number> <day> <out>
"""
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app', 'engine'))
sys.path.insert(0, os.path.join(ROOT, 'research'))
from sowtool import crypto, save as sv                # noqa: E402
from sowtool.gamedata import GameData                 # noqa: E402
import orc_insert                                     # noqa: E402


def history(t, starts, end, number, rec):
    """Token indexes of the day values of an orc's history events."""
    k = next(i for i, s in enumerate(starts) if t[s + 1].value == number)
    e = starts[k + 1] if k + 1 < len(starts) else end
    return [i + 1 for i in range(starts[k], e - 1) if t[i].type == 0 and t[i].value and t[i + 1].type == 3
            and rec(t[i].value)]


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    path, num, day, out_p = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
    gd = GameData(os.path.join(ROOT, 'app', 'gui', 'data', 'game.gamedb'),
                  os.path.join(ROOT, 'app', 'gui', 'data', 'string_ruru.strdb'))
    rec = gd.record
    buf, _ = sv.load(path)
    p, t, mg, n, starts, end = orc_insert.table(buf, rec)
    cells = history(t, starts, end, num, rec)
    out = bytearray(buf)
    for i in cells:
        struct.pack_into('<h', out, t[i].pos + 1, day)
    print('№%d: событий истории %d, дни %s -> %d' % (num, len(cells), sorted({t[i].value for i in cells}), day))
    for i in cells:
        print('   %-48s %d -> %d' % (rec(t[i - 1].value), t[i].value, day))
    out = bytes(out)
    sv.validate(out, 'результат')
    sv.write(out_p, out, crypto.user_id_from_name(out_p))
    print('Записано:', out_p)
