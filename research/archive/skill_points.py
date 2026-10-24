"""Set Talion's unspent skill points (research / for tests).

    python research/skill_points.py <save> <out> <points>

The points are the stock entry SkillPoint in Talion's IVMG data: 0c 01 | 00 SkillPoint | 04 <count> | 04 0 | 04 0
(as ngplus.build writes it); the stock table is rebuilt the same way.
"""
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app', 'engine'))
from sowtool import crypto, ngplus, save as sv       # noqa: E402

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    path, out_p, points = sys.argv[1], sys.argv[2], int(sys.argv[3])
    buf, _ = sv.load(path)
    inv = sv.Inventory(buf)
    print('очков было:', inv.stock_count(ngplus.SKILL_POINT))
    entries = [buf[s:e] for rid, _, _, _, s, e in inv.stock if rid != ngplus.SKILL_POINT]
    if points:
        entries.append(b'\x0c\x01\x00' + struct.pack('<I', ngplus.SKILL_POINT) + b'\x04' + struct.pack('<i', points)
                       + b'\x04\x00\x00\x00\x00\x04\x00\x00\x00\x00')
    t = inv.t
    blob = buf[t[0].pos:t[3].pos] + b'\x04' + struct.pack('<i', len(entries)) + b''.join(entries) + \
        buf[t[inv.stock_end_tok].pos:inv.blob_end]
    p, size = sv.block(buf, 'IVMG')
    bt = inv.t[0].pos - 5
    ivmg = buf[p + 20:bt] + b'\x10' + struct.pack('<I', len(blob)) + blob + buf[inv.blob_end:p + 16 + size]
    out = sv.replace_block(buf, 'IVMG', ivmg)
    sv.validate(out, 'результат')
    print('очков стало:', sv.Inventory(out).stock_count(ngplus.SKILL_POINT))
    assert '_ShadowOfWar' in os.path.basename(out_p), 'имя выхода должно содержать _ShadowOfWar (ключ шифрования)'
    sv.write(out_p, out, crypto.user_id_from_name(out_p))
    print('Записано:', out_p, 'пользователь %08x' % sv.load(out_p)[1])
