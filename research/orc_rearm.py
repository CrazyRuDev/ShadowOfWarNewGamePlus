"""Experiment: a dead orc of the save gets another "cheated death" return (research).

    python research/orc_rearm.py <save> <out> <number> <ResReward_*> [--role Role_X] [--timer seconds]

Flags IsDead + CanResurrect + PresentedToPlayer + IdentityPresented, one reward in the reward list at the record end
(an existing list is replaced), optionally a new role (00 Role_* of the description, same size), and a
CheatDeath_Ambush in the event queue for the orc's region.
"""
import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app', 'engine'))
sys.path.insert(0, os.path.join(ROOT, 'research'))
from sowtool import crypto, save as sv                # noqa: E402
from sowtool.gamedata import GameData, name_hash      # noqa: E402
import orc_insert                                     # noqa: E402
import orc_ghosts                                     # noqa: E402


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    path, out_p, num, reward = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
    role, timer = arg('--role'), int(arg('--timer', '20'))
    gd = GameData(os.path.join(ROOT, 'app', 'gui', 'data', 'game.gamedb'),
                  os.path.join(ROOT, 'app', 'gui', 'data', 'string_ruru.strdb'))
    rec = gd.record
    buf, _ = sv.load(path)
    p, t, mg, n, starts, end = orc_insert.table(buf, rec)
    k = next(i for i, s in enumerate(starts) if t[s + 1].value == num)
    a = t[starts[k]].pos
    b = t[starts[k + 1]].pos if k + 1 < len(starts) else t[end].pos
    raw = bytearray(buf[a:b])
    rt = sv.tokens(bytes(raw), 0, len(raw))
    region = rec(rt[4].value)                         # 0c 01 | 04 n | 09 | 08 name | 00 Faction_<region>
    npc = next(i for i, x in enumerate(rt) if x.type == 0x0F and '_NPC_' in x.value)
    f = next(x for x in rt[npc:] if x.type == 0x05)
    flags = int.from_bytes(raw[f.pos + 1:f.pos + 9], 'little')
    for bit in orc_ghosts.FLAGS:
        flags |= 1 << bit
    raw[f.pos + 1:f.pos + 9] = flags.to_bytes(8, 'little')
    if role:
        r = next(x for x in rt[npc:] if x.type == 0 and (rec(x.value) or '').startswith('Role_'))
        print('роль %s -> %s' % (rec(r.value), role))
        raw[r.pos + 1:r.pos + 5] = struct.pack('<I', name_hash(role))
    # reward list: ... 04 <n> (00 ResReward_*)*n | 04 x | 00 0 | 02 n | 00 <role or 0>
    cnt = None
    for i in range(len(rt) - 4, 0, -1):
        if rt[i].type == 4 and all(rt[i + 1 + j].type == 0 and (rec(rt[i + 1 + j].value) or '').startswith('ResReward_')
                                   for j in range(rt[i].value)) and rt[i + 1 + rt[i].value].type == 4 \
                and rt[i + 2 + rt[i].value].type == 0 and rt[i + 3 + rt[i].value].type == 2:
            cnt = i
            break
    old = [rec(rt[cnt + 1 + j].value) for j in range(rt[cnt].value)]
    new_list = b'\x04' + struct.pack('<i', 1) + b'\x00' + struct.pack('<I', name_hash(reward))
    raw = raw[:rt[cnt].pos] + new_list + raw[rt[cnt + rt[cnt].value].end:]
    print('№%d %s: флаги смерти и воскрешения, награда %s -> %s, засада через %d с (%s)'
          % (num, rec(rt[3].value) if False else '', old or 'нет', reward, timer, region))
    event = (b'\x0c\x01' + b'\x00' + struct.pack('<I', name_hash(region)) + b'\x00' +
             struct.pack('<I', name_hash('CheatDeath_Ambush')) + b'\x00' + struct.pack('<I', name_hash(region)) +
             b'\x04' + struct.pack('<i', num) + b'\x08' + struct.pack('<I', 0) + b'\x04' + struct.pack('<i', timer * 1000))
    q = [i for i in range(len(t) - 7) if t[i].type == 0x0C and t[i].value == 1 and t[i + 1].type == 0
         and (rec(t[i + 1].value) or '').startswith('Faction_') and t[i + 2].type == 0 and t[i + 3].type == 0
         and t[i + 4].type == 4 and t[i + 5].type == 8 and t[i + 6].type == 4]
    c = t[q[0] - 1]
    assert c.type == 4 and c.value == len(q)
    at = t[q[0]].pos
    assert b <= at
    out = bytearray(buf[:a] + bytes(raw) + buf[b:at] + event + buf[at:])
    d_rec = len(raw) - (b - a)
    struct.pack_into('<i', out, c.pos + d_rec + 1, c.value + 1)
    d = d_rec + len(event)
    bp, size = sv.block(buf, 'WHDC')
    struct.pack_into('<I', out, bp + 8, size + d)
    struct.pack_into('<I', out, bp + 16, size + d - 4)
    out = sv.fix_lengths(out, d)
    sv.validate(out, 'результат')
    sv.write(out_p, out, crypto.user_id_from_name(out_p))
    print('Записано:', out_p)
