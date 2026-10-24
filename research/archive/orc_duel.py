"""Experiment 38: a duel for a place — an orc of the finished game, without a place, challenges a captain.

    python research/orc_duel.py <save> <source> <source orc number> <out> [<captain number>]

The save's own duel mission (a Nemesis "power struggle" entry in WHDC) is moved to Nurn, the only region of the
act 2 start: 00 Faction | 00 Duel | 00 <place> | 00 <place> | 04 <mission id> | 04 <state> | 00 <header> | 00 x4 |
05 | 05 | 04 <roles> | (00 <role> | 00 <role>_0N | 00 | 00 Faction | 04 <orc> | 02 | 02 | 02 | 00) x roles.
Faction -> Faction_island, place MI_Duel_00 -> IS_Duel_00, header -> PowerStruggle_Act2 (the one Nurn's missions
use), the challenger (PS_Subject_Cap_Duel) = the source orc, put in Nurn without a place (alive, HasEverSpawned,
history days = the base's day - 5), the other (PS_Other_Cap_Duel) = a living Nurn captain. Same sizes but the orc
appended to MainGame (orc_ghosts.prepare, as in experiments 10-16).
"""
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app', 'engine'))
sys.path.insert(0, os.path.join(ROOT, 'research'))
from sowtool import crypto, ngplus, orcs, save as sv     # noqa: E402
from sowtool.gamedata import GameData, name_hash         # noqa: E402
import orc_ghosts                                        # noqa: E402
import orc_insert                                        # noqa: E402

H = lambda s: struct.pack('<I', name_hash(s))


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    path, src_p, num, out_p = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
    gd = GameData(os.path.join(ROOT, 'app', 'gui', 'data', 'game.gamedb'),
                  os.path.join(ROOT, 'app', 'gui', 'data', 'string_ruru.strdb'))
    rec = gd.record
    buf = sv.load(path)[0]
    source = sv.load(src_p)[0]
    army = {o['number']: o for o in orcs.read(buf, gd)}
    who = {o['number']: o for o in orcs.read(source, gd)}[num]
    # the orc: appended to MainGame, Nurn, no place
    p, t, mg, n, starts, end = orc_insert.table(buf, rec)
    day = max(0, ngplus.base_day(buf) - 5)
    raw, _, days = orc_ghosts.prepare(orc_insert.record(source, rec, num), n, 'Faction_island', None, rec, day)
    at = t[end].pos
    out = bytearray(buf[:at] + raw + buf[at:])
    struct.pack_into('<i', out, t[mg + 2].pos + 1, n + 1)
    bp, size = sv.block(buf, 'WHDC')
    struct.pack_into('<I', out, bp + 8, size + len(raw))
    struct.pack_into('<I', out, bp + 16, size + len(raw) - 4)
    out = bytearray(sv.fix_lengths(out, len(raw)))
    print('орк: %s %s (источник №%d, ур. %d) -> №%d, Нурн, без места, дни истории %d (%d событий)'
          % (who['name'], who['title'], num, who['level'], n, day, days))
    # the duel mission
    t = sv.block_tokens(bytes(out), 'WHDC')
    i = next(i for i in range(len(t)) if t[i].type == 0 and rec(t[i].value) == 'PS_Subject_Cap_Duel')
    assert rec(t[i - 13].value) == 'Duel' and rec(t[i - 14].value).startswith('Faction_')
    captains = [o for o in army.values() if o['place_key'].startswith('island_Row_Captain') and not o['dead']
                and not o['story']]
    other = army[int(sys.argv[5])] if len(sys.argv) > 5 else sorted(captains, key=lambda o: o['level'])[0]
    edits = {i - 14: H('Faction_island'), i - 12: H('IS_Duel_00'), i - 11: H('IS_Duel_00'),
             i - 8: H('PowerStruggle_Act2'), i + 3: H('Faction_island'), i + 12: H('Faction_island')}
    for k, v in edits.items():
        assert t[k].type == 0
        out[t[k].pos + 1:t[k].pos + 5] = v
    assert t[i + 4].type == 4 and rec(t[i + 9].value) == 'PS_Other_Cap_Duel' and t[i + 13].type == 4
    print('дуэль №%d: было %s, %s против %s' % (t[i - 10].value, rec(t[i - 14].value),
                                               army[t[i + 4].value]['name'], army[t[i + 13].value]['name']))
    struct.pack_into('<i', out, t[i + 4].pos + 1, n)
    struct.pack_into('<i', out, t[i + 13].pos + 1, other['number'])
    print('стало: Нурн, IS_Duel_00, %s %s (№%d) вызывает капитана %s %s (№%d, ур. %d, %s)'
          % (who['name'], who['title'], n, other['name'], other['title'], other['number'], other['level'],
             other['place_key'].split('_Row_')[1]))
    out = bytes(out)
    sv.validate(out, 'результат')
    os.makedirs(os.path.dirname(os.path.abspath(out_p)), exist_ok=True)
    sv.write(out_p, out, crypto.user_id_from_name(out_p))
    assert sv.load(out_p)[1] == 0x096c2a9f
    print('Записано:', out_p)


if __name__ == '__main__':
    main()
