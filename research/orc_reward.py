"""Experiment: change a waiting orc's resurrection reward and spread the CheatDeath_Ambush timers (research).

    python research/orc_reward.py <save> <out> [<number>:<ResReward_*> ...] [--timers 20,110,200]

Rewards are replaced in place (00 <hash>, same size). --timers sets the CheatDeath_Ambush timers (seconds) of the
waiting orcs in queue order.
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
    path, out_p = sys.argv[1], sys.argv[2]
    timers = [int(x) for x in sys.argv[sys.argv.index('--timers') + 1].split(',')] if '--timers' in sys.argv else []
    pairs = [a for a in sys.argv[3:] if ':' in a]
    gd = GameData(os.path.join(ROOT, 'app', 'gui', 'data', 'game.gamedb'),
                  os.path.join(ROOT, 'app', 'gui', 'data', 'string_ruru.strdb'))
    rec = gd.record
    buf, _ = sv.load(path)
    out = bytearray(buf)
    p, t, mg, n, starts, end = orc_insert.table(buf, rec)
    for a in pairs:
        num, reward = int(a.split(':')[0]), a.split(':')[1]
        k = next(i for i, s in enumerate(starts) if t[s + 1].value == num)
        e = starts[k + 1] if k + 1 < len(starts) else end
        cells = [i for i in range(starts[k], e) if t[i].type == 0 and (rec(t[i].value) or '').startswith('ResReward_')]
        assert len(cells) == 1, cells
        old = rec(t[cells[0]].value)
        struct.pack_into('<I', out, t[cells[0]].pos + 1, name_hash(reward))
        print('№%d: награда %s -> %s' % (num, old, reward))
    if timers:
        q = [i for i in range(len(t) - 7) if t[i].type == 0x0C and t[i].value == 1 and t[i + 1].type == 0
             and t[i + 2].type == 0 and rec(t[i + 2].value) == 'CheatDeath_Ambush' and t[i + 4].type == 4
             and t[i + 5].type == 8 and t[i + 6].type == 4]
        for i, s in zip(q, timers):
            print('засада орка №%d: таймер %d мс -> %d с' % (t[i + 4].value, t[i + 6].value, s))
            struct.pack_into('<i', out, t[i + 6].pos + 1, s * 1000)
    out = bytes(out)
    sv.validate(out, 'результат')
    sv.write(out_p, out, crypto.user_id_from_name(out_p))
    print('Записано:', out_p)
