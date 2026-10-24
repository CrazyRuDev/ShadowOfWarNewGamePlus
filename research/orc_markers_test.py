"""Experiment 64: two markers of the game on orcs that come by the exact ambush "the orc changed" (research).

    python research/orc_markers_test.py <live save> <source> <out>

On the player's save (act 2, Nurn): two living orcs of the source not in the save yet, level 28, the ambush
RoleTransformation_Ambush (it came to the second in experiment 61) at 2 and 4 minutes:
  - Marker_Generate_BloodBrother — the game should make it a blood brother (who avenges it when it is killed);
  - Marker_LearnSpeed_VeryFast instead of its own learn speed — it should adapt to Talion's attacks fast.
"""
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app', 'engine'))
sys.path.insert(0, os.path.join(ROOT, 'research'))
from sowtool import crypto, orcs, returned, save as sv     # noqa: E402
from sowtool.gamedata import GameData, name_hash            # noqa: E402
import orc_ambush20                                         # noqa: E402
import orc_ghosts                                           # noqa: E402

LEVEL = 28
TESTS = [('Marker_Generate_BloodBrother', None, 120), ('Marker_LearnSpeed_VeryFast', 'Marker_LearnSpeed_', 240)]


def marker(raw, add, replace, rec):
    """Replace the marker starting with `replace` by `add` (in every place it is), or add `add`."""
    t = sv.tokens(raw, 0, len(raw))
    hits = [x for x in t if replace and x.type == 0 and (rec(x.value) or '').startswith(replace)]
    if not hits:
        return returned.add_traits(raw, [], [add], rec)
    raw = bytearray(raw)
    for x in hits:
        raw[x.pos + 1:x.pos + 5] = struct.pack('<I', name_hash(add))
    return bytes(raw)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    live_p, src_p, out_p = sys.argv[1:4]
    gd = GameData(os.path.join(ROOT, 'app', 'gui', 'data', 'game.gamedb'),
                  os.path.join(ROOT, 'app', 'gui', 'data', 'string_ruru.strdb'))
    rec = gd.record
    live, source = sv.load(live_p)[0], sv.load(src_p)[0]
    pairs = {(o['name'], o['title']) for o in orcs.read(live, gd)}       # names repeat: name and title
    living = [o for o in orcs.read(source, gd)
              if not o['dead'] and not o['follower'] and not o['story'] and o['class'] != 'олог'
              and (o['name'], o['title']) not in pairs and o['title']]
    living.sort(key=lambda o: (o['met'], o['level']), reverse=True)
    out, real = live, orc_ghosts.prepare
    for (add, replace, sec), o in zip(TESTS, living):
        def prepare(raw, number, region, reward, rec_, day=1, add=add, replace=replace):
            raw, src_region, days = real(raw, number, region, reward, rec_, day)
            raw = orc_ambush20.fix(raw, rec_, None, LEVEL, False, True)
            return marker(raw, add, replace, rec_), src_region, days
        orc_ghosts.prepare = prepare
        out = bytes(orc_ghosts.build(out, source, [(o['number'], '@RoleTransformation_Ambush')], 'Faction_island', gd,
                                     log=lambda *a: None, first=sec * 1000, step=1))
        print('через %d мин  %s %s, ур. %d — %s' % (sec // 60, o['name'], o['title'], LEVEL, add))
    sv.validate(out, 'результат')
    os.makedirs(os.path.dirname(os.path.abspath(out_p)), exist_ok=True)
    sv.write(out_p, out, crypto.user_id_from_name(out_p))
    assert sv.load(out_p)[1] == 0x096c2a9f
    print('Записано:', out_p)


if __name__ == '__main__':
    main()
