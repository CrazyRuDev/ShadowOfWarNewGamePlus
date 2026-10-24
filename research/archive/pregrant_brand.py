"""Experiment: «Подчинение» (Brand) already granted in a new game+ on the act 2 base (research).

    python research/pregrant_brand.py <save> <out>

The act 2 start script grants Brand on the first save after loading and then the unspent skill points are gone.
Here the save gets the records the game itself writes for it (seen in the user's save 22:33:27): stock entries
PS_Brand_UNLOCK, PS_Brand_DUMMY, S_Brand = 1; IVPD PS_Brand_UNLOCK, PS_Brand_DUMMY = 1, PS_Drain_Child2_SKILL = 0.
To see whether the script then leaves the points alone, and what the game does with a story skill already learned.
"""
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app', 'engine'))
from sowtool import crypto, ngplus, save as sv       # noqa: E402
from sowtool.gamedata import name_hash               # noqa: E402

STOCK = ('PS_Brand_UNLOCK', 'PS_Brand_DUMMY', 'S_Brand')
IVPD = {'PS_Brand_UNLOCK': 1, 'PS_Brand_DUMMY': 1, 'PS_Drain_Child2_SKILL': 0}

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    path, out_p = sys.argv[1], sys.argv[2]
    buf, _ = sv.load(path)
    inv = sv.Inventory(buf)
    have = {rid for rid, *_ in inv.stock}
    entries = [buf[s:e] for _, _, _, _, s, e in inv.stock]
    for n in STOCK:
        if name_hash(n) not in have:
            entries.append(b'\x0c\x01\x00' + struct.pack('<I', name_hash(n)) + b'\x04\x01\x00\x00\x00'
                           + b'\x04\x00\x00\x00\x00\x04\x00\x00\x00\x00')
            print('запасы: +', n)
    t = inv.t
    blob = buf[t[0].pos:t[3].pos] + b'\x04' + struct.pack('<i', len(entries)) + b''.join(entries) + \
        buf[t[inv.stock_end_tok].pos:inv.blob_end]
    p, size = sv.block(buf, 'IVMG')
    ivmg = buf[p + 20:inv.t[0].pos - 5] + b'\x10' + struct.pack('<I', len(blob)) + blob + buf[inv.blob_end:p + 16 + size]
    buf = sv.replace_block(buf, 'IVMG', ivmg)

    before, pairs, after = ngplus._ivpd_pairs(buf)
    ids = {name_hash(n): v for n, v in IVPD.items()}
    pairs = [(rid, raw[:6] + struct.pack('<i', ids[rid]) if rid in ids else raw) for rid, raw in pairs]
    for n, v in IVPD.items():
        if name_hash(n) not in {rid for rid, _ in pairs}:
            pairs.append((name_hash(n), b'\x00' + struct.pack('<I', name_hash(n)) + b'\x04' + struct.pack('<i', v)))
            print('IVPD: +', n, v)
    before = bytearray(before)
    struct.pack_into('<i', before, len(before) - 4, len(pairs))
    buf = sv.replace_block(buf, 'IVPD', bytes(before) + b''.join(raw for _, raw in pairs) + after)

    sv.validate(buf, 'результат')
    print('очки навыков:', sv.Inventory(buf).stock_count(ngplus.SKILL_POINT))
    assert '_ShadowOfWar' in os.path.basename(out_p), 'имя выхода должно содержать _ShadowOfWar (ключ шифрования)'
    sv.write(out_p, buf, crypto.user_id_from_name(out_p))
    print('Записано:', out_p, 'пользователь %08x' % sv.load(out_p)[1])
