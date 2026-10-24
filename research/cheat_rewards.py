"""The game's own table "death cause -> possible resurrection rewards" (research).

Records MaybeNewRole_CheatDeath_<cause> (game.gamedb): name | type word | 0x08000007 | 1 | references
(list << 20 | index) to Faction/Rewards/Definitions (ResReward_*). The causes are groups of the death record's
Resurrection_<cause> (e.g. LeftArmLower_Removed -> ArmSever).

    python research/cheat_rewards.py
"""
import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app', 'engine'))
from sowtool.gamedata import GameData                 # noqa: E402

REWARDS_LIST = 0x294          # list number of Faction/Rewards/Definitions in references (game 1.0.8874)


def table(gd):
    """{cause group: [ResReward_*]}"""
    db, pool = gd.db, gd.pool
    base = 0x47 + len(pool)
    rewards = gd.category('Faction/Rewards/Definitions')
    out = {}
    for name in sorted(set(re.findall(r'MaybeNewRole_CheatDeath_[A-Za-z0-9_]+', pool.decode('latin1')))):
        po = pool.find(b'\x00' + name.encode() + b'\x00') + 1
        for m in re.finditer(re.escape(struct.pack('<I', po)), db[base:]):
            p = base + m.start()
            if p % 4:
                continue
            word, flags = struct.unpack_from('<II', db, p + 4)
            if flags != 0x08000007:
                continue
            refs, q = [], p + 16                      # (the word at +12 is not the count) references until the next
            while q + 4 <= len(db):                   # record: every one points into the rewards list
                r = struct.unpack_from('<I', db, q)[0]
                if r >> 20 != REWARDS_LIST or (r & 0xFFFFF) >= len(rewards):
                    break
                refs.append(rewards[r & 0xFFFFF][1])
                q += 4
            if refs:
                out[name[len('MaybeNewRole_CheatDeath_'):]] = refs
                break
    return out


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    gd = GameData(os.path.join(ROOT, 'app', 'gui', 'data', 'game.gamedb'),
                  os.path.join(ROOT, 'app', 'gui', 'data', 'string_ruru.strdb'))
    for cause, rew in table(gd).items():
        print('%-18s %s' % (cause, ', '.join(r.replace('ResReward_', '') for r in rew)))
