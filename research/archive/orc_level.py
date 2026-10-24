"""Experiment: set orcs' levels (research). Same size, in place.

    python research/orc_level.py <save> <out> <orc number>:<level> [...]

The level is stored twice, as level-1, right in the description: 0f <id>_NPC_ | 09 | 04 | 04 | 04 | 0c | 0f | 0f |
08 <level-1> | 04 <level-1> (equal in every orc of four saves, 1524 orcs). The Cheat Engine table of SeiKur0
(таблицы/shadowofwar_seikur0_v21.ct, "Adjust uruk level") changes only the orc's "Level-1" in memory, the game
shows Level-1 + <bonus at +470> + 1 and derives the rest.
"""
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app', 'engine'))
from sowtool import crypto, orcs, save as sv          # noqa: E402
from sowtool.gamedata import GameData                 # noqa: E402


def level_tokens(t, s, e):
    npc = next(i for i in range(s, e - 9) if t[i].type == 0x0F and t[i + 1].type == 9 and t[i + 5].type == 0x0C
               and t[i + 6].type == 0x0F and t[i + 7].type == 0x0F and t[i + 8].type == 8)
    assert t[npc + 9].type == 4
    return t[npc + 8], t[npc + 9]


def set_levels(buf, rec, levels):
    """(new save, [(orc number, old level)])"""
    t, ranges = orcs.table(buf, rec)
    out, changed = bytearray(buf), []
    for s, e in ranges:
        num = t[s + 1].value
        if num not in levels:
            continue
        a, b = level_tokens(t, s, e)
        struct.pack_into('<I', out, a.pos + 1, levels[num] - 1)
        struct.pack_into('<i', out, b.pos + 1, levels[num] - 1)
        changed.append((num, a.value + 1))
    return bytes(out), changed


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    path, out_p = sys.argv[1], sys.argv[2]
    levels = {int(a.split(':')[0]): int(a.split(':')[1]) for a in sys.argv[3:]}
    gd = GameData(os.path.join(ROOT, 'app', 'gui', 'data', 'game.gamedb'),
                  os.path.join(ROOT, 'app', 'gui', 'data', 'string_ruru.strdb'))
    buf, user = sv.load(path)
    out, changed = set_levels(buf, gd.record, levels)
    for num, old in changed:
        print('№%d: уровень %d -> %d' % (num, old, levels[num]))
    sv.validate(out, 'результат')
    assert '_ShadowOfWar' in os.path.basename(out_p), 'имя выхода должно содержать _ShadowOfWar (ключ шифрования)'
    sv.write(out_p, out, crypto.user_id_from_name(out_p))
    print('Записано:', out_p, 'пользователь %08x' % sv.load(out_p)[1])
