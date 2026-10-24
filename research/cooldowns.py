"""Nemesis ambush cooldowns in a save: show them or reset some to "never used" (research).

    python research/cooldowns.py <save>                               (show)
    python research/cooldowns.py <save> <out> Periodic_Ambush_Cooldown General_Cooldown ...   (reset)

Entry (WHDC, next to the event queue): 04 <game time, ms> | 00 <Faction/Ambush/Chance record> | 04 <times used> |
04 <ms since the last use>. Never used: count 0 and the last value equal to the game time.
"""
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app', 'engine'))
from sowtool import crypto, save as sv                # noqa: E402
from sowtool.gamedata import GameData                 # noqa: E402


def entries(buf, gd):
    """{name: (token index of the game time, tokens)}"""
    rec = gd.record
    chance = {n for _, n in gd.category('Faction/Ambush/Chance')}
    p, size = sv.block(buf, 'WHDC')
    t = sv.tokens(buf, p + 20, p + 16 + size)
    out = {}
    for i in range(1, len(t) - 2):
        if t[i].type == 0 and t[i - 1].type == 4 and t[i + 1].type == 4 and t[i + 2].type == 4:
            n = rec(t[i].value)
            if n in chance:
                out[n] = (i, t)
    return out


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    gd = GameData(os.path.join(ROOT, 'app', 'gui', 'data', 'game.gamedb'),
                  os.path.join(ROOT, 'app', 'gui', 'data', 'string_ruru.strdb'))
    buf, _ = sv.load(sys.argv[1])
    es = entries(buf, gd)
    if len(sys.argv) < 4:
        for n, (i, t) in sorted(es.items()):
            if t[i + 1].value:
                print('%-44s раз %-3d с последнего %.1f мин' % (n, t[i + 1].value, t[i + 2].value / 60000))
        sys.exit(0)
    out = bytearray(buf)
    for n in sys.argv[3:]:
        i, t = es[n]
        struct.pack_into('<i', out, t[i + 1].pos + 1, 0)
        struct.pack_into('<i', out, t[i + 2].pos + 1, t[i - 1].value)
        print('%s: было %d раз, %.1f мин назад -> никогда' % (n, t[i + 1].value, t[i + 2].value / 60000))
    out = bytes(out)
    sv.validate(out, 'результат')
    sv.write(sys.argv[2], out, crypto.user_id_from_name(sys.argv[2]))
    print('Записано:', sys.argv[2])
