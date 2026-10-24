"""Experiment: set the level of Talion's items (research). Same size, in place.

    python research/item_level.py <save> <out> <level> [all]

Without "all" only the equipped items. Items of level 1 (looks, story items) are left as they are. Item record in
Talion's IVMG data: 0c 01 | 04 <number> | 04 <level> | 02 ? | 00 <template> ... (the level as shown, not level-1).
"""
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app', 'engine'))
from sowtool import crypto, save as sv               # noqa: E402

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    path, out_p, level = sys.argv[1], sys.argv[2], int(sys.argv[3])
    buf, _ = sv.load(path)
    inv = sv.Inventory(buf)
    take = None if 'all' in sys.argv[4:] else set(inv.equipped)
    t = inv.t
    out = bytearray(buf)
    for k in range(inv.stock_end_tok + 1, len(t) - 4):
        if t[k].type == 0x0C and t[k].value == 1 and t[k + 1].type == 4 and t[k + 2].type == 4 \
                and t[k + 3].type == 2 and t[k + 4].type == 0 and 0 < t[k + 1].value < 1000000 \
                and 1 < t[k + 2].value < 100 and (take is None or t[k + 1].value in take):
            print('предмет №%d: уровень %d -> %d' % (t[k + 1].value, t[k + 2].value, level))
            struct.pack_into('<i', out, t[k + 2].pos + 1, level)
    out = bytes(out)
    sv.validate(out, 'результат')
    assert '_ShadowOfWar' in os.path.basename(out_p), 'имя выхода должно содержать _ShadowOfWar (ключ шифрования)'
    sv.write(out_p, out, crypto.user_id_from_name(out_p))
    print('Записано:', out_p, 'пользователь %08x' % sv.load(out_p)[1])
