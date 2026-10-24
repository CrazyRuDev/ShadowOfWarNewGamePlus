"""Experiment: put an orc on a hierarchy place held by a dead orc (research).

    python research/orc_slot.py <save> <orc number> <out> [<dead orc number>]

The place is the state token after the AI class (00 <region>_Row_<rank>); the dead holder gets 0 (no place),
the orc gets the holder's place. Same sizes, nothing moves.
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
import orcs2                                          # noqa: E402


def hierarchy(t, rec, region):
    """The region's hierarchy table: 00 Faction_<region> | 04 a | 04 b | 04 rows | (00 <region>_Row_* | 04 places |
    04 orc or -1 per place) * rows. Returns {row name: [token index of each place]}."""
    out = {}
    for i in range(len(t) - 4):
        if t[i].type == 0 and rec(t[i].value) == 'Faction_' + region and t[i + 1].type == 4 and t[i + 2].type == 4 \
                and t[i + 3].type == 4 and t[i + 4].type == 0 and (rec(t[i + 4].value) or '').startswith(region + '_Row_'):
            j = i + 4
            for _ in range(t[i + 3].value):
                row, places = rec(t[j].value), t[j + 1].value
                out[row] = list(range(j + 2, j + 2 + places))
                j += 2 + places
            return out
    raise SystemExit('нет таблицы иерархии для %s' % region)


def slot_token(t, starts, number):
    """Index of the place token of an orc: 0c 01 | 04 n | 09 | 08 name | 00 faction | 00 faction | 00 AI | 00 place."""
    s = next(s for s in starts if t[s + 1].value == number)
    assert t[s + 7].type == 0
    return s + 7


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    path, num, out_p = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    gd = GameData(os.path.join(ROOT, 'app', 'gui', 'data', 'game.gamedb'),
                  os.path.join(ROOT, 'app', 'gui', 'data', 'string_ruru.strdb'))
    rec = gd.record
    buf, _ = sv.load(path)
    os_ = {o['number']: o for o in orcs2.orcs(buf, gd) if o.get('number') is not None}
    me = os_[num]
    region = me['faction'].replace('Faction_', '')
    dead = [o for o in os_.values() if 'IsDead' in o['flags'] and (o.get('slot') or '').startswith(region + '_Row_')]
    holder = os_[int(sys.argv[4])] if len(sys.argv) > 4 else sorted(dead, key=lambda o: o['slot'])[0]
    p, t, mg, n, starts, end = orc_insert.table(buf, rec)
    a, b = slot_token(t, starts, holder['number']), slot_token(t, starts, num)
    out = bytearray(buf)
    place = buf[t[a].pos + 1:t[a].pos + 5]
    row = rec(struct.unpack('<I', place)[0])
    out[t[b].pos + 1:t[b].pos + 5] = place
    out[t[a].pos + 1:t[a].pos + 5] = b'\0\0\0\0'
    # the hierarchy table is what the game goes by: the holder's number there becomes the orc's
    cells = hierarchy(t, rec, region)[row]
    cell = next(c for c in cells if t[c].value == holder['number'])
    struct.pack_into('<i', out, t[cell].pos + 1, num)
    print('ряд %s, места: %s' % (row, [t[c].value for c in cells]))
    print('место %s: мёртвый №%d %s снят, на его место — №%d %s (запись орка и таблица иерархии)'
          % (row, holder['number'], holder['name'], num, me['name']))
    out = bytes(out)
    sv.validate(out, 'результат')
    sv.write(out_p, out, crypto.user_id_from_name(out_p))
    print('Записано:', out_p)
