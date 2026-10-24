"""Experiment: set Talion's level (research). Same size, in place; the XP in the level becomes 0.

    python research/talion_level.py <save> <out> <level>

PPDC: 00 SinglePlayer | 04 <level-1> | 04 <xp in the level> (as ngplus.build writes it).
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
    out = bytearray(buf)
    pt = sv.block_tokens(buf, 'PPDC')
    for i, tok in enumerate(pt):
        if tok.type == 0 and tok.value == sv.TALION:
            struct.pack_into('<i', out, pt[i + 1].pos + 1, level - 1)
            struct.pack_into('<i', out, pt[i + 2].pos + 1, 0)
    out = bytes(out)
    print('Талион: %s -> %s' % (sv.talion(buf), sv.talion(out)))
    sv.validate(out, 'результат')
    assert '_ShadowOfWar' in os.path.basename(out_p), 'имя выхода должно содержать _ShadowOfWar (ключ шифрования)'
    sv.write(out_p, out, crypto.user_id_from_name(out_p))
    print('Записано:', out_p, 'пользователь %08x' % sv.load(out_p)[1])
