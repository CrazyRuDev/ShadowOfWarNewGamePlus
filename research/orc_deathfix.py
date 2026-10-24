"""Experiment: fix the death record of waiting "cheated death" orcs (research).

    python research/orc_deathfix.py <save> <out> [--player <n>,...] [--drop-pending <n>,...] [--timers n:s,...]

Death record (after the history): 00 Resurrection_<cause> | 03 day | 03 day | 04 <killer: -1 = Talion, else orc
number> | 00 <killer model: Player_Character / Orc_*> | 00 <kill animation> | 0c | 0c | 03 | 04 | 04 | 04 <pending
events> | (0c 01 | 00 <event> | 00 Faction | 04 orc | 00 Faction | 04 orc) * pending | ...
--player: the killer becomes Talion (04 -1, Player_Character, PC_Bip_LastWordsKill_CombatFinish), an orc-made
cause becomes the matching player one (Resurrection_OrcSlash -> Resurrection_PlayerSlash).
--drop-pending: the pending events of the record are removed (they point at orc numbers of the source game).
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

PLAYER_CAUSE = {'Resurrection_OrcSlash': 'Resurrection_PlayerSlash', 'Resurrection_OrcArrow': 'Resurrection_PlayerArrow',
                'Resurrection_OrcClub': 'Resurrection_PlayerSlash', 'Resurrection_SlaveSlash': 'Resurrection_PlayerSlash'}


def death(t, s, e, rec):
    """Token index of 00 Resurrection_<cause> of the death record (the one followed by 03 03 04 00 00)."""
    return next(i for i in range(s, e - 6) if t[i].type == 0 and (rec(t[i].value) or '').startswith('Resurrection_')
                and t[i + 1].type == 3 and t[i + 2].type == 3 and t[i + 3].type == 4 and t[i + 4].type == 0)


def arg(name):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else ''


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    path, out_p = sys.argv[1], sys.argv[2]
    player = [int(x) for x in arg('--player').split(',') if x]
    drop = [int(x) for x in arg('--drop-pending').split(',') if x]
    timers = dict((int(a.split(':')[0]), int(a.split(':')[1])) for a in arg('--timers').split(',') if a)
    gd = GameData(os.path.join(ROOT, 'app', 'gui', 'data', 'game.gamedb'),
                  os.path.join(ROOT, 'app', 'gui', 'data', 'string_ruru.strdb'))
    rec = gd.record
    buf, _ = sv.load(path)
    p, t, mg, n, starts, end = orc_insert.table(buf, rec)
    out = bytearray(buf)
    cuts = []                                         # (start, end) byte ranges to remove
    for num in sorted(set(player) | set(drop)):
        k = next(i for i, s in enumerate(starts) if t[s + 1].value == num)
        e = starts[k + 1] if k + 1 < len(starts) else end
        d = death(t, starts[k], e, rec)
        if num in player:
            cause = rec(t[d].value)
            new_cause = PLAYER_CAUSE.get(cause, cause)
            struct.pack_into('<I', out, t[d].pos + 1, name_hash(new_cause))
            struct.pack_into('<i', out, t[d + 3].pos + 1, -1)
            struct.pack_into('<I', out, t[d + 4].pos + 1, name_hash('Player_Character'))
            struct.pack_into('<I', out, t[d + 5].pos + 1, name_hash('PC_Bip_LastWordsKill_CombatFinish'))
            print('№%d: убийца %s/%s -> Талион, %s -> %s' % (num, t[d + 3].value, rec(t[d + 4].value), cause, new_cause))
        if num in drop:
            c = d + 11                                # 04 <pending events>
            assert t[c].type == 4, t[c]
            cnt = t[c].value
            j = c + 1
            for _ in range(cnt):
                assert t[j].type == 0x0C and t[j].value == 1
                j += 6                        # 0c 01 | 00 event | 00 F | 04 n | 00 F | 04 n
            struct.pack_into('<i', out, t[c].pos + 1, 0)
            cuts.append((t[c + 1].pos, t[j].pos))
            print('№%d: убрано незавершённых событий: %d (%s)' % (num, cnt, rec(t[c + 2].value) if cnt else '-'))
    q = [i for i in range(len(t) - 7) if t[i].type == 0x0C and t[i].value == 1 and t[i + 2].type == 0
         and rec(t[i + 2].value) == 'CheatDeath_Ambush' and t[i + 4].type == 4 and t[i + 6].type == 4]
    for i in q:
        if t[i + 4].value in timers:
            struct.pack_into('<i', out, t[i + 6].pos + 1, timers[t[i + 4].value] * 1000)
            print('засада №%d: таймер -> %d с' % (t[i + 4].value, timers[t[i + 4].value]))
    for a, b in sorted(cuts, reverse=True):
        del out[a:b]
    d = sum(b - a for a, b in cuts)
    if d:
        bp, size = sv.block(buf, 'WHDC')
        struct.pack_into('<I', out, bp + 8, size - d)
        struct.pack_into('<I', out, bp + 16, size - d - 4)
        out = bytearray(sv.fix_lengths(out, -d))
    out = bytes(out)
    sv.validate(out, 'результат')
    sv.write(out_p, out, crypto.user_id_from_name(out_p))
    print('Записано:', out_p)
