"""Experiment 65: does the orc level hook of the SeiKur0 table reach an orc that already exists (research).

    python research/orc_level_hook_test.py <live save> <source> <out folder>

On the player's save (act 2, Nurn): one living orc of the source not in the save yet, level 28, the exact ambush
RoleTransformation_Ambush at 1 minute (experiments 61, 64). Next to the save goes a Cheat Engine table with only the
«Adjust uruk level» script of SeiKur0 (`таблицы/shadowofwar_seikur0_v21.ct`, the injection ShadowOfWar.exe+2CDA85 in
the current exe), both limits set to LEVEL_HOOK: if the orc comes at that level, a plugin can set the level of our
orcs when they appear.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app', 'engine'))
sys.path.insert(0, os.path.join(ROOT, 'research'))
from sowtool import crypto, orcs, save as sv                # noqa: E402
from sowtool.gamedata import GameData                       # noqa: E402
import orc_ambush20                                         # noqa: E402
import orc_ghosts                                           # noqa: E402

LEVEL, LEVEL_HOOK, SECONDS = 28, 60, 60
TABLE = os.path.join(ROOT, 'таблицы', 'shadowofwar_seikur0_v21.ct')


def ce_table(path):
    """The «Adjust uruk level» script of SeiKur0 alone, its limits (dd max, dd min) both LEVEL_HOOK."""
    s = open(TABLE, encoding='utf-8').read()
    i = s.index('<Description>"Adjust uruk level"</Description>')
    a, b = s.index('<AssemblerScript>', i), s.index('</AssemblerScript>', i)
    script = s[a + len('<AssemblerScript>'):b]
    script, n = re.subn(r'val_lvl:\s*dd \(int\)\d+\s*dd \(int\)\d+',
                        'val_lvl:\ndd (int)%d\ndd (int)%d' % (LEVEL_HOOK, LEVEL_HOOK), script)
    assert n == 1
    with open(path, 'w', encoding='utf-8') as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n<CheatTable CheatEngineTableVersion="45">\n  <CheatEntries>\n'
                '    <CheatEntry>\n      <ID>1</ID>\n      <Description>"Уровень орков = %d (SeiKur0, опыт 65)"'
                '</Description>\n      <VariableType>Auto Assembler Script</VariableType>\n      <AssemblerScript>'
                '%s</AssemblerScript>\n    </CheatEntry>\n  </CheatEntries>\n</CheatTable>\n' % (LEVEL_HOOK, script))


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    live_p, src_p, out_dir = sys.argv[1:4]
    gd = GameData(os.path.join(ROOT, 'app', 'gui', 'data', 'game.gamedb'),
                  os.path.join(ROOT, 'app', 'gui', 'data', 'string_ruru.strdb'))
    live, source = sv.load(live_p)[0], sv.load(src_p)[0]
    pairs = {(o['name'], o['title']) for o in orcs.read(live, gd)}       # names repeat: name and title
    living = [o for o in orcs.read(source, gd)
              if not o['dead'] and not o['follower'] and not o['story'] and o['class'] != 'олог'
              and (o['name'], o['title']) not in pairs and o['title']]
    living.sort(key=lambda o: (o['met'], o['level']), reverse=True)
    o = living[0]
    real = orc_ghosts.prepare

    def prepare(raw, number, region, reward, rec_, day=1):
        raw, src_region, days = real(raw, number, region, reward, rec_, day)
        return orc_ambush20.fix(raw, rec_, None, LEVEL, False, True), src_region, days
    orc_ghosts.prepare = prepare
    out = bytes(orc_ghosts.build(live, source, [(o['number'], '@RoleTransformation_Ambush')], 'Faction_island', gd,
                                 log=lambda *a: None, first=SECONDS * 1000, step=1))
    sv.validate(out, 'результат')
    os.makedirs(out_dir, exist_ok=True)
    out_p = os.path.join(out_dir, '096c2a9f_ShadowOfWar.sav')
    sv.write(out_p, out, crypto.user_id_from_name(out_p))
    assert sv.load(out_p)[1] == 0x096c2a9f
    ce_table(os.path.join(out_dir, 'уровень орков 60.CT'))
    print('через %d с  %s %s, в сохранении ур. %d; с таблицей должен прийти %d' % (SECONDS, o['name'], o['title'],
                                                                                LEVEL, LEVEL_HOOK))
    print('Записано:', out_dir)


if __name__ == '__main__':
    main()
