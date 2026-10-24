; Shadow of War: новая игра+ — окно программы (AutoHotkey v2).
; Сохранения читает и собирает движок (Python, engine\sowtool), окно только показывает его данные. Две сборки
; (app\build.bat): папка — SoWNGPlus.exe = неизменённый AutoHotkey64.exe (сам запускает SoWNGPlus.ahk рядом) и
; встраиваемый Python в python\ — для раздачи (VirusTotal 0); один файл — exe Ahk2Exe с движком PyInstaller внутри
; (tools\single_ahk.py дописывает FileInstall в копию скрипта) — для себя: антивирусы его помечают (VirusTotal 4–7/71).
; Важно: AutoHotkey не различает регистр имён переменных (tiles и Tiles — одна переменная).
#Requires AutoHotkey v2.0
#SingleInstance Force

global APP_DIR := A_ScriptDir
global CHRON_DIR := APP_DIR "\летопись", ChronPid := 0
global INI := APP_DIR "\SoWNGPlus.ini"
global DATA_DIR := APP_DIR "\data"



; ---- цвета в духе игрового меню ------------------------------------------------------------------------
global C_BG := "0E1116", C_PANEL := "171C24", C_CARD := "1D2430", C_TEXT := "D8DDE4", C_DIM := "7A8494"
global C_BLUE := "4FC3F7", C_ON := "2E4A63", C_OFF := "1E232B"
global C_LGND := "B58CFF", C_EPIC := "D77CFF", C_RARE := "6FA8FF", C_SET := "E0605A"

global Rows := []        ; [{title, learned, total, nodes:[{skills:[{name, learned, child, rank, key, text}]}]}]
global Items := []       ; [{uid, level, slot, rarity, equipped, name, owner, line, desc, effects:[{kind, text}]}]
global Gems := []
global World := {act1: "", regions: [], collections: []}   ; хэдиры и коллекции (вкладка «Мир»)
global Talion := {level: "", xp: "", xp_next: "", mirians: "", points: ""}
global CurrentSlot := 1
global HelpMap := Map()   ; hwnd -> текст всплывающей подсказки

global MAX_ROWS := 6, MAX_NODES := 8, MAX_KIDS := 4, MAX_EFFECTS := 8, ShownEffects := 0
global FreezeDepth := 0, FreezeAreas := [], FreezeSent := false
global SLOTS := ["меч", "кинжал", "лук", "доспехи", "плащ", "руна"]
global SLOT_TITLES := ["Меч", "Кинжал", "Лук", "Доспехи", "Плащ", "Руна"]

; ---- окно ------------------------------------------------------------------------------------------------
G := Gui("+Resize +MinSize1100x700", "Shadow of War — новая игра+")
G.BackColor := C_BG
G.SetFont("s10 c" C_TEXT, "Segoe UI")
G.OnEvent("Close", (*) => ExitApp())
OnExit((*) => (StopChronicle(), 0))           ; при любом выходе (трей, перезапуск скрипта), не только по крестику
G.OnEvent("Size", OnSize)

G.SetFont("s16 bold c" C_TEXT)
G.Add("Text", "x20 y12 w380", "НОВАЯ ИГРА+")
G.SetFont("s14 bold c" C_TEXT)
MiriansText := G.Add("Text", "x900 y14 w360 Right", "")
G.SetFont("s10 norm c" C_TEXT)
G.Add("Text", "x20 y52 w84 c" C_DIM, "Сохранение:")
HelpMark(104, 50, "Сохранение пройденной игры: его содержимое видно на вкладках, и из него переносится прогресс.`n"
    . "Файл называется <8 знаков>_ShadowOfWar.sav (Steam, папка Steam\userdata\<номер>\356190\remote)`n"
    . "или <имя компьютера>_ShadowOfWar.sav (другие версии игры).")
SaveEdit := G.Add("Edit", "x128 y48 w700 h24 Background" C_PANEL " c" C_TEXT, IniRead(INI, "paths", "save", ""))
BtnOpen := G.Add("Button", "x820 y47 w110 h26", "Открыть…")
BtnOpen.OnEvent("Click", PickSave)
BtnSteam := G.Add("Button", "x940 y47 w140 h26", "Найти в Steam")
BtnSteam.OnEvent("Click", (*) => FindSteam(true))
BtnRead := G.Add("Button", "x1090 y47 w110 h26", "Прочитать")
BtnRead.OnEvent("Click", (*) => LoadSave())
AddHelp(BtnOpen, "Выбрать файл сохранения вручную (для любой версии игры).")
AddHelp(BtnSteam, "Найти в Steam папку игры и самое свежее сохранение.")
AddHelp(BtnRead, "Перечитать сохранение (например, после того как вы поиграли).")
StatusText := G.Add("Text", "x420 y18 w460 c" C_DIM, "")

Tabs := G.Add("Tab3", "x10 y84 w1260 h690", ["Навыки", "Предметы", "Мир", "Орки", "Новая игра+", "Настройка"])

; ---- вкладка «Навыки» ------------------------------------------------------------------------------------
Tabs.UseTab(1)
G.SetFont("s15 bold")
G.Add("Text", "x30 y122 w200", "НАВЫКИ")
G.SetFont("s10 norm")
LevelText := G.Add("Text", "x30 y152 w500", "Уровень Талиона: —")
XpBar := G.Add("Progress", "x30 y176 w300 h10 Background" C_PANEL " c" C_BLUE, 0)
XpText := G.Add("Text", "x340 y172 w300 c" C_DIM, "")

RowPanels := [], RowLabels := [], RowCounts := [], SkillTiles := [], Connectors := []   ; Connectors[(r-1)*MAX_NODES+n]
Loop MAX_ROWS {
    r := A_Index
    RowPanels.Push(G.Add("Text", "x26 y200 w770 h88 Background" C_PANEL))
    G.SetFont("s10 bold")
    RowLabels.Push(G.Add("Text", "x34 y200 w110 BackgroundTrans", ""))
    G.SetFont("s15 bold c" C_BLUE)
    RowCounts.Push(G.Add("Text", "x34 y222 w110 BackgroundTrans", ""))
    G.SetFont("s8 norm c" C_TEXT)
    rowNodes := []
    Loop MAX_NODES {
        n := A_Index
        nodeTiles := []
        Connectors.Push(G.Add("Text", "x0 y0 w3 h10 Hidden Background" C_DIM))
        Loop MAX_KIDS + 1 {
            k := A_Index
            c := G.Add("Text", "x0 y0 w10 h10 +Border Center Hidden Background" C_OFF, "")
            c.OnEvent("Click", ShowSkill.Bind(r, n, k))
            nodeTiles.Push(c)
        }
        rowNodes.Push(nodeTiles)
    }
    SkillTiles.Push(rowNodes)
}
G.SetFont("s10 norm c" C_TEXT)
SkPanel := G.Add("Text", "x810 y122 w440 h640 Background" C_PANEL)
G.SetFont("s14 bold")
SkillName := G.Add("Text", "x830 y140 w400 h60 BackgroundTrans", "")
G.SetFont("s10 norm c" C_BLUE)
SkillState := G.Add("Text", "x830 y205 w400 BackgroundTrans", "")
G.SetFont("s10 norm c" C_TEXT)
SkillDesc := G.Add("Text", "x830 y240 w400 h300 BackgroundTrans", "Выберите навык.")

; ---- вкладка «Предметы» ----------------------------------------------------------------------------------
Tabs.UseTab(2)
G.SetFont("s15 bold")
G.Add("Text", "x30 y122 w200", "ПРЕДМЕТЫ")
G.SetFont("s9 norm")
SlotTiles := []
Loop SLOTS.Length {
    i := A_Index
    c := G.Add("Text", "x30 y160 w122 h64 +Border Center Background" C_OFF, SLOT_TITLES[i])
    c.OnEvent("Click", SelectSlot.Bind(i))
    SlotTiles.Push(c)
}
G.SetFont("s10 norm c" C_BLUE)
SlotCaption := G.Add("Text", "x30 y236 w760", "")
G.SetFont("s10 norm c" C_TEXT)
ItemList := G.Add("ListView", "x30 y260 w760 h500 -Multi Background" C_PANEL " c" C_TEXT,
    ["", "Название", "Ур.", "Редкость", "Прежний владелец", "uid"])
ItemList.ModifyCol(1, 24), ItemList.ModifyCol(2, 300), ItemList.ModifyCol(3, "50 Integer"), ItemList.ModifyCol(4, 110)
ItemList.ModifyCol(5, 250), ItemList.ModifyCol(6, 0)
ItemList.OnEvent("ItemSelect", (lv, row, sel) => sel ? ShowItem(lv.GetText(row, 6)) : 0)

ItPanel := G.Add("Text", "x810 y122 w440 h400 Background" C_PANEL)
G.SetFont("s9 bold c" C_BLUE)
ItemTag := G.Add("Text", "x830 y135 w400 BackgroundTrans", "")
G.SetFont("s15 bold c" C_TEXT)
ItemName := G.Add("Text", "x830 y155 w300 h30 BackgroundTrans", "")
G.SetFont("s20 bold c" C_TEXT)
ItemLevel := G.Add("Text", "x1130 y150 w110 Right BackgroundTrans", "")
G.SetFont("s10 norm c" C_DIM)
ItemLine := G.Add("Text", "x830 y188 w400 BackgroundTrans", "")
G.SetFont("s10 norm c" C_TEXT)
ItemDesc := G.Add("Text", "x830 y212 w400 h40 BackgroundTrans", "")
EffectCards := [], EffectTiles := []
Loop MAX_EFFECTS {
    EffectCards.Push(G.Add("Text", "x830 y260 w400 h40 Hidden Background" C_CARD))
    EffectTiles.Push(G.Add("Text", "x842 y266 w376 h30 Hidden BackgroundTrans", ""))
}
OwnerCard := G.Add("Text", "x830 y600 w400 h48 Hidden Background" C_CARD)
ItemOwner := G.Add("Text", "x842 y606 w376 h38 Hidden BackgroundTrans c" C_TEXT, "")
G.SetFont("s10 bold")
GemTitle := G.Add("Text", "x810 y532 w440", "Самоцветы в запасе")
G.SetFont("s10 norm")
GemList := G.Add("ListView", "x810 y556 w440 h204 -Multi Background" C_PANEL " c" C_TEXT, ["Самоцвет", "Кол-во"])
GemList.ModifyCol(1, 330), GemList.ModifyCol(2, "80 Integer")

; ---- вкладка «Мир» ---------------------------------------------------------------------------------------
Tabs.UseTab(3)
G.SetFont("s15 bold")
G.Add("Text", "x30 y122 w600", "МИР")
G.SetFont("s10 norm")
WorldAct := G.Add("Text", "x30 y152 w1200 c" C_DIM, "")
G.Add("Text", "x30 y184 w600", "Регионы")
HelpMark(110, 182, "Хэдиры — башни региона (по 3 в каждом). Итильдин — слова для двери могильника региона (по 6).`n"
    . "«Известно слов» — сколько слов игра уже показывает в загадке двери, «вставлено» — сколько стоит на двери.`n"
    . "Игра ведёт ещё и свои счётчики по регионам (их она показывает как «x из N»). Если счётчик расходится`n"
    . "с подобранным, рядом в скобках указано «в игре N». Артефакты и воспоминания игра считает только по регионам.")
RegionList := G.Add("ListView", "x30 y208 w1200 h170 -Multi NoSortHdr Background" C_PANEL " c" C_TEXT,
    ["Регион", "Хэдиры", "Итильдин", "Дверь: известно слов", "Дверь: вставлено", "Артефакты (счётчик)", "Воспоминания (счётчик)"])
G.Add("Text", "x30 y396 w600", "Коллекции")
HelpMark(124, 394, "Подобрано в этом сохранении из всего, что есть в игре.`n"
    . "Гондорские артефакты игра считает ещё и отдельным счётчиком — он должен совпадать с числом подобранных.")
CollList := G.Add("ListView", "x30 y420 w1200 h130 -Multi NoSortHdr Background" C_PANEL " c" C_TEXT,
    ["Коллекция", "Подобрано", "Всего", "Примечание"])

; ---- вкладка «Орки» --------------------------------------------------------------------------------------
Tabs.UseTab(4)
G.SetFont("s15 bold")
G.Add("Text", "x30 y122 w300", "ОРКИ")
G.SetFont("s10 norm")
OrcSummary := G.Add("Text", "x30 y150 w1200 h52 c" C_DIM, "")
G.Add("Text", "x30 y212 w60", "Поиск:")
OrcSearch := G.Add("Edit", "x90 y208 w260 h24 Background" C_PANEL " c" C_TEXT, "")
OrcSearch.OnEvent("Change", (*) => FillOrcs())
AddHelp(OrcSearch, "Показать только орков, в имени или титуле которых есть этот текст.")
HelpMark(360, 210, "Все орки армии Немезиды из сохранения, по группам. Группу можно свернуть или развернуть`n"
    . "щелчком по её заголовку, список — отсортировать щелчком по заголовку столбца.`n"
    . "«Счёт» — насколько орк докучал Талиону: убил Талиона ×3, довёл до последнего шанса ×3,`n"
    . "сбежал или выжил в бою ×1, вернулся из мёртвых ×2. Опасность = счёт + опасные особенности`n"
    . "(«Без шансов» всегда +3; остальные веса программа считает по вашему же сохранению: во сколько раз особенность`n"
    . "чаще у орков, убивавших Талиона, чем у остальных встречавшихся, — от +0,5 до +2; вместе не больше +5;`n"
    . "если убийц меньше 8 — веса по опыту игры на высшей сложности). Веса видны строкой над списком.`n"
    . "«Рекомендованы к переносу» — до 15 самых опасных орков со счётом от 5 (встречались с Талионом, что-то ему`n"
    . "сделали, не сюжетные), бывшие последователи тоже. Уровень задаёт карточка «Враги из пройденной игры».`n"
    . "Куда: в Нурн, а при начале после пролога — в Нурн и Кирит-Унгол; самые опасные становятся вождями.`n"
    . "Убитые Талионом возвращаются «обманувшими смерть» (облик, шрамы и реплика по причине гибели),`n"
    . "живые и убитые другими орками — живыми, как были. Переносит карточка «Враги из пройденной игры» (вкладка «Новая игра+»).")
OrcList := G.Add("ListView", "x30 y242 w800 h510 -Multi Background" C_PANEL " c" C_TEXT,
    ["Орк", "Ур.", "Сост.", "Регион", "Место", "Класс", "Племя", "Редкость", "Счёт", "Убил Т.", "Посл. шанс",
     "Сбегал", "Возвр.", "Гибели", "Перенос", "Куда", "№"])
OrcList.OnEvent("ItemSelect", (lv, row, sel) => sel ? ShowOrc(lv.GetText(row, 17)) : 0)
for c in [2, 9, 10, 11, 12, 13, 14, 17]
    OrcList.ModifyCol(c, "Integer")
OrcInfo := G.Add("Edit", "x850 y122 w400 h630 ReadOnly -E0x200 Background" C_PANEL " c" C_TEXT, "Выберите орка.")
global OrcData := []                 ; [{group, num, cells:[...], info}]
; сюжетные (перенос сломал бы прохождение) и не встречавшиеся с Талионом (пустые, счёт 0) не показываются
global ORC_GROUPS := ["Рекомендованы к переносу", "Живые враги", "Мёртвые враги", "Последователи Талиона"]

; ---- вкладка «Новая игра+» -------------------------------------------------------------------------------
Tabs.UseTab(5)
G.SetFont("s15 bold")
G.Add("Text", "x30 y122 w600", "СОБРАТЬ НОВУЮ ИГРУ+")
G.SetFont("s10 norm")
NgSource := G.Add("Text", "x30 y156 w1200 c" C_DIM, "Пройденная игра: (откройте сохранение вверху)")
G.Add("Text", "x30 y192 w220", "Опорное сохранение (новая игра):")
HelpMark(250, 190, "Опорное сохранение — начало новой игры. В него переносится прогресс Талиона из пройденной игры`n"
    . "(навыки, снаряжение, самоцветы, мирианы), настройки игры и открытые облики, и всё, что выбрано в карточках`n"
    . "ниже. Сюжет и мир остаются как в опорном сохранении. Армия Немезиды — из вашей пройденной игры: случайных`n"
    . "капитанов и вождей опоры заменяют её живые враги на своих местах (в своём регионе), а остальные места —`n"
    . "орки пройденной игры, которые не встречали Талиона.`n"
    . "Опорные сохранения идут с программой (папка bases): сразу после пролога (обучение и завязка сюжета заново)`n"
    . "или начало второго акта (первый акт с обучением пройден, впереди Немезида и почти весь сюжет).`n"
    . "Начало после пролога даёт больше места врагам из пройденной игры: Нурн и Кирит-Унгол (на втором акте — только Нурн).`n"
    . "Только эти два: их содержимое известно и проверено, на случайных сохранениях середины сюжета сборка могла бы`n"
    . "сломать задания.")
; готовые опоры: [подпись, файл в папке bases]
BASES := [["Сразу после пролога", "prologue_ShadowOfWar.sav"],
          ["Начало второго акта", "act2_ShadowOfWar.sav"]]
choices := []
for b in BASES
    choices.Push(b[1])
baseIdx := IniRead(INI, "paths", "base_choice", "1")
baseIdx := IsInteger(baseIdx) && baseIdx >= 1 && baseIdx <= choices.Length ? Integer(baseIdx) : 1
BaseChoice := G.Add("DropDownList", "x280 y188 w340 Choose" baseIdx, choices)
BaseChoice.OnEvent("Change", (*) => UpdatePlan())
G.Add("Text", "x30 y228 w220", "Куда записать:")
HelpMark(250, 226, "Файл, который получит игра. Чтобы игра его увидела, он должен называться как её сохранение:`n"
    . "в Steam <8 знаков>_ShadowOfWar.sav (папка ...\356190\remote), в других версиях <имя компьютера>_ShadowOfWar.sav.`n"
    . "Перед заменой отключите облачную синхронизацию Steam для игры.")
OutEdit := G.Add("Edit", "x280 y224 w800 h24 Background" C_PANEL, IniRead(INI, "paths", "out", ""))
BtnOut := G.Add("Button", "x1090 y223 w110 h26", "Обзор…")
BtnOut.OnEvent("Click", PickOut)
BackupBox := G.Add("CheckBox", "x280 y256 w600 Checked", "Сохранить копию заменяемого файла (.bak с датой)")
AddHelp(BackupBox, "Перед записью старый файл копируется рядом, например 096c2a9f_ShadowOfWar.sav.20261020-153000.bak.`n"
    . "Чтобы вернуть его, удалите .sav и переименуйте копию обратно.")

; карточки настроек: группа, ключ, заголовок, включена ли по умолчанию, подробное описание
global CARDS := [], CARD_GROUPS := ["ТАЛИОН", "МИР", "АРМИЯ"], GroupHeads := Map()
global SelectedCard := ""
global CardScroll := 0, CardView := [30, 300, 760, 790]      ; прокрутка карточек: x, y, ширина, низ видимой части
for grp in CARD_GROUPS {               ; не «g»: имена без учёта регистра, g — это окно G
    G.SetFont("s10 bold c" C_BLUE)
    GroupHeads[grp] := G.Add("Text", "x30 y300 w400 h22", grp)
    G.SetFont("s10 norm c" C_TEXT)
}
AddCard("ТАЛИОН", "start", "Начать с уровня новой игры", true,
    "Уровень Талиона и всего его снаряжения — надетого и в инвентаре — понижается: при начале второго акта до "
    . "среднего уровня капитанов Нурна минус 2, при начале после пролога — до первого уровня. Так бой с капитаном "
    . "становится вызовом с первой минуты.`r`n`r`n"
    . "Навыки переносятся все, кроме трёх, которые в своё время выдаст сюжет: «Подчинение капитанов», «Подчинение» "
    . "и «Хуже смерти»; очки навыков не переносятся. "
    . "Предметы со всеми свойствами, самоцветы и мирианы переносятся. Урон и цифры свойств игра "
    . "пересчитывает от уровня предмета; в игре любой предмет можно улучшить до уровня Талиона. Уровни Талион "
    . "зарабатывает заново и получает за них очки навыков, как обычно.")
AddCard("ТАЛИОН", "clean", "Убрать обычное и редкое снаряжение", true,
    "Обычное и редкое снаряжение обычно только захламляет инвентарь, поэтому его можно очистить.`r`n`r`n"
    . "Обычные и редкие предметы, которые не надеты, не переносятся. Остаются высшие и легендарные предметы, всё "
    . "надетое и сюжетные вещи (лук Аскар, глефа, кольца, ножны).")
AddCard("МИР", "towers", "Захваченные башни (хэдиры)", true,
    "Прогресс захвата хэдиров будет таким же, как в пройденной игре.`r`n`r`n"
    . "При начале после пролога в Минас-Моргуле переносятся два хэдира из трёх: третий сюжет сам даёт захватить в "
    . "задании пролога. При начале второго акта в Минас-Моргуле будут захвачены те же хэдиры, что в пройденной игре.`r`n`r`n"
    . "На карте отмечается всё неподобранное, что показывают хэдиры: итильдин — в регионе, где захвачены все 3 "
    . "хэдира; гондорские артефакты и воспоминания Шелоб — когда захвачены все хэдиры мира.")
AddCard("МИР", "ithildin", "Итильдин", true,
    "Переносятся слова итильдина, подобранные в пройденной игре, все, во всех регионах, Минас-Моргул тоже. "
    . "Вещи в могильниках и сюжетные предметы не переносятся.")
AddCard("МИР", "gondor", "Гондорские артефакты", true,
    "Переносятся гондорские артефакты, подобранные в пройденной игре. Если там подобраны все, один артефакт не "
    . "перенесётся, чтобы не сломать завершение этого испытания.")
AddCard("МИР", "shelob", "Воспоминания Шелоб", true,
    "Переносятся воспоминания Шелоб, найденные в пройденной игре. Если там найдены все, одно не перенесётся: за все "
    . "воспоминания игра открывает способность, и это должно произойти в самой игре.")
AddCard("АРМИЯ", "twenty", "Враги из пройденной игры", true,
    "Привет из прошлого: орки, которые больше всех докучали Талиону (вкладка «Орки», «Рекомендованы к переносу»), "
    . "возвращаются за ним в новую игру. Список «Сколько» под карточкой: 3, 5 (по умолчанию), 10 или 15 — места "
    . "раздаются по важности:`r`n"
    . "1–3. Три самых опасных — в Нурне, первом регионе новой игры после Минас-Моргула: самый опасный встретит вас "
    . "засадой, как только придёте в Нурн (убитый Талионом — «обманул смерть», живой — «орк изменился»), двое "
    . "других — капитанами Нурна: их, как всех капитанов, "
    . "знающих Талиона, игра сама пошлёт за вами. Всем троим игра охотнее даст снова обмануть смерть.`r`n"
    . "4. Главный босс Горгорота, 5. босс Серегоста — засадой, как только войдёте в регион. Боссы — те, кто чаще всех "
    . "убивал Талиона; их черты — как в пройденной игре, но без слабостей, страхов и «Нет последнего шанса».`r`n"
    . "6 и дальше — капитаны на карте: Кирит-Унгол (при начале после пролога), затем Нурн.`r`n"
    . "Уровень — верх уровней своего региона +10…15: сильнее любого местного, но не стена. Сверх того — два "
    . "бывших последователя, погибших в пройденной игре, вернутся предателями через 2,5–4 часа: те, кто служил "
    . "Талиону дольше и больше всех (дни службы, задания, убитые капитаны, сколько раз Талион их спасал, место).`r`n`r`n"
    . "Убитые Талионом возвращаются «обманувшими смерть»: при встрече орк скажет реплику о своей "
    . "гибели. Награду за возвращение выбирает таблица самой игры по причине смерти: огонь — «Пламя Войны», яд — "
    . "«Гибельный», разрублен пополам — «Мясорубка», отрубленная рука — «Клешня» с протезом, отрубленная голова — "
    . "«Железный Череп», клинок — один из шрамов по весам игры. Облик, раны на лице и теле, голос и черты — как при "
    . "настоящем возвращении. Живые и убитые другими орками приходят живыми, как были.`r`n`r`n"
    . "Список «Слабости» убирает выбранные слабости у всех, кроме боссов (у них их нет и так). Засада ждёт, пока "
    . "вы придёте в её регион; если не приходит — отбегите от места прошлой засады. Остальные места регионов "
    . "достаются армии: живым врагам пройденной игры на их местах, затем новым оркам.`r`n`r`n"
    . "Список «Память» — для новой игры+ из новой игры+. Всё, что орки помнят из прошлых игр, программа помечает "
    . "при переносе, и на следующем круге счёт считает это прошлое по выбору: вполовину (по умолчанию: ветеран "
    . "остаётся, если и в этот раз докучал, иначе уступает новым), только последний круг (каждый раз свежие враги) "
    . "или всё, что было (старый враг лишь растёт). Для первой новой игры+ из обычного прохождения почти не важно.")
G.SetFont("s10 norm c" C_TEXT)
; уровень и слабости двадцатки: [ключ движка, подпись]
global TW_COUNTS := [["3", "3"], ["5", "5"], ["10", "10"], ["15", "15"]], TwPlan := Map()
global TW_WEAK := [["none", "Ничего не убирать"], ["fatal", "Убрать фатальные слабости"], ["fears", "Убрать страхи"],
    ["plain", "Убрать простые слабости"], ["all", "Убрать все слабости и страхи"]]
global TW_HISTORY := [["decay", "Прошлые круги — вполовину"], ["last", "Только последний круг"],
    ["all", "Всё, что было"]]
TwLevelLabel := G.Add("Text", "x0 y0 w70 h22 BackgroundTrans c" C_DIM, "Сколько:")
TwLevel := G.Add("DropDownList", "x0 y0 w190 Choose" IniChoice("twenty_count", TW_COUNTS, "5"), Labels(TW_COUNTS))
TwWeakLabel := G.Add("Text", "x0 y0 w80 h22 BackgroundTrans c" C_DIM, "Слабости:")
TwWeak := G.Add("DropDownList", "x0 y0 w230 Choose" IniChoice("twenty_weak", TW_WEAK), Labels(TW_WEAK))
TwHistLabel := G.Add("Text", "x0 y0 w70 h22 BackgroundTrans c" C_DIM, "Память:")
TwHist := G.Add("DropDownList", "x0 y0 w250 Choose" IniChoice("twenty_history", TW_HISTORY, "decay"), Labels(TW_HISTORY))
AddHelp(TwLevel, "Сколько врагов вернётся: 3 — три самых опасных в Нурне, 5 — ещё два босса (Горгорот, Серегост),`n"
    . "10 и 15 — больше знакомых капитанов. Меньше достойных в пройденной игре — придёт меньше.")
AddHelp(TwWeak, "Какие слабости убрать у врагов из пройденной игры: фатальные (мгновенная смерть), страхи (страх и ужас),`n"
    . "простые (уязвимости и ошеломление) или все сразу.")
TwLevel.OnEvent("Change", (*) => (ShowTwentyPlan(), SelectCard("twenty")))
TwWeak.OnEvent("Change", (*) => SelectCard("twenty"))
AddHelp(TwHist, "Для новой игры+ из новой игры+: как считать то, что орки помнят из прошлых игр.`n"
    . "Вполовину — ветеран остаётся, только если и в этот раз докучал; только последний круг — свежие враги;`n"
    . "всё, что было — старый враг лишь растёт. Меняет и список «Рекомендованы к переносу» на вкладке «Орки».")
TwHist.OnEvent("Change", (*) => ChangeHistory())
CardScrollBar := G.Add("Slider", "x0 y0 w24 h100 Vertical NoTicks Range0-0 Hidden", 0)
CardScrollBar.OnEvent("Change", CardScrollMove)
BtnBuild := G.Add("Button", "x30 y756 w300 h36 Default", "Собрать сохранение")
BtnBuild.OnEvent("Click", BuildNGPlus)
AddHelp(BtnBuild, "Переносятся навыки (кроме трёх, их выдаст сюжет), снаряжение, самоцветы и мирианы — и всё, что выбрано в карточках.`n"
    . "Слоты самоцветов остаются пустыми — обучение попросит вставить самоцвет.")
; справа: подробное описание выбранной карточки и журнал сборки
DetailPanel := G.Add("Text", "x810 y300 w440 h300 Background" C_PANEL)
G.SetFont("s13 bold c" C_TEXT)
DetailTitle := G.Add("Text", "x830 y312 w400 h28 BackgroundTrans", "")
G.SetFont("s10 norm c" C_TEXT)
DetailText := G.Add("Edit", "x830 y346 w400 h240 ReadOnly -E0x200 Background" C_PANEL " c" C_TEXT, "")
G.SetFont("s10 bold c" C_DIM)
LogTitle := G.Add("Text", "x810 y612 w440", "Журнал сборки")
G.SetFont("s10 norm c" C_TEXT)
NgLog := G.Add("Edit", "x810 y636 w440 h150 ReadOnly -Wrap +HScroll Background" C_PANEL " c" C_TEXT, "")
LayoutCards(30, 300, 760, 790)
UpdateCardStates()
SelectCard("start")

; ---- вкладка «Настройка» ---------------------------------------------------------------------------------
Tabs.UseTab(6)
G.SetFont("s15 bold")
G.Add("Text", "x30 y122 w600", "ДАННЫЕ ИГРЫ")
G.SetFont("s10 norm")
SetHelp := G.Add("Text", "x30 y160 w1200 h40 c" C_DIM,
    "Названия навыков и предметов берутся из файлов игры. Для Steam папка находится сама; для другой версии "
    . "укажите папку игры (где ShadowOfWar.exe или папка x64) и нажмите «Распаковать» — один раз.")
G.Add("Text", "x30 y210 w110", "Папка игры:")
HelpMark(140, 208, "Папка, где установлена игра (в ней папка x64 и архивы .arch06).`n"
    . "В Steam: ...\steamapps\common\ShadowOfWar. Нужна один раз — чтобы достать названия и тексты.")
GameEdit := G.Add("Edit", "x170 y206 w910 h24 Background" C_PANEL, IniRead(INI, "paths", "game", ""))
BtnGame := G.Add("Button", "x1090 y205 w110 h26", "Обзор…")
BtnGame.OnEvent("Click", PickGame)
BtnSetup := G.Add("Button", "x170 y246 w300 h34", "Распаковать данные игры")
BtnSetup.OnEvent("Click", (*) => SetupData())
AddHelp(BtnSetup, "Достаёт из архивов игры базу и русские тексты в папку data рядом с программой (около минуты).")
SetupLog := G.Add("Edit", "x30 y296 w1200 h200 ReadOnly Background" C_PANEL " c" C_TEXT, "")
DataState := G.Add("Text", "x30 y510 w1200 c" C_DIM, "")
G.SetFont("s15 bold")
ChronTitle := G.Add("Text", "x30 y560 w600", "ЛЕТОПИСЬ (ДЛЯ ОТЛАДКИ)")
G.SetFont("s10 norm")
ChronHelp := G.Add("Text", "x30 y596 w1200 h60 c" C_DIM,
    "Пока вы играете, программа следит за сохранением и записывает коротко только важное: что стало с орками пройденной "
    . "игры (пришёл, погиб, убил Талиона, вернулся, повышен, предал), засады в очереди Немезиды, шаги сюжета, уровень "
    . "Талиона, вылеты игры и нечитаемые сохранения. Копии сохранения: последние 30 и навсегда — в важные моменты. "
    . "Сохранение игры только читается. Если что-то пошло не так — пришлите папку летописи.")
BtnChron := G.Add("Button", "x30 y664 w300 h34", "Включить летопись")
BtnChron.OnEvent("Click", (*) => ToggleChronicle())
BtnChronDir := G.Add("Button", "x340 y664 w200 h34", "Открыть папку")
BtnChronDir.OnEvent("Click", (*) => (DirCreate(CHRON_DIR), Run(CHRON_DIR)))
ChronState := G.Add("Text", "x30 y708 w1200 c" C_DIM, "Летопись выключена.")
AddHelp(BtnChron, "Следит за сохранением, в которое записана новая игра+ (поле «Куда записать» на вкладке «Новая игра+»),`n"
    . "а если его нет — за самым свежим сохранением Steam. Орков пройденной игры берёт из сохранения вверху окна.`n"
    . "Работает, пока открыта программа; закрытие программы её останавливает.")
Tabs.UseTab()

OnMessage(0x200, OnMouseMove)
OnMessage(0x20A, OnCardWheel)
G.Show("w1300 h820 Maximize")
; раскладка под настоящий размер сразу: событие Size дойдёт только после Startup (чтение сохранения и армии),
; а до того вкладки были бы нарисованы под стартовые 1300×820
G.GetClientPos(, , &cw, &ch), Layout(cw, ch)
UpdateDataState()
Startup()

; ---- без мерцания: окно не рисуется, пока меняется много элементов, потом перерисовывается один раз ----------
; (WS_EX_COMPOSITED для всего окна ломает вкладки Tab3; заморозка на смену вкладки роняет программу на вкладках со
; списками — обе проверены 2026-10-23 и убраны). Заморозка вложенная: перерисовка —
; когда отпущена последняя, только областей, названных в Thaw (без них — всё окно).
Freeze() {
    global FreezeDepth, FreezeSent
    ; только показанное окно: WM_SETREDRAW true делает окно видимым — до G.Show оно бы появилось раньше времени
    if FreezeDepth++ = 0 && (FreezeSent := DllCall("IsWindowVisible", "Ptr", G.Hwnd))
        SendMessage(0x000B, 0, 0, G)                  ; WM_SETREDRAW false
}
Thaw(ctrls*) {
    global FreezeDepth, FreezeAreas, FreezeSent
    if FreezeDepth = 0                                ; не заморожено (вкладку сменили не мышью) — нечего
        return
    if !ctrls.Length
        FreezeAreas.Push(0)                           ; 0 — всё окно
    for c in ctrls
        FreezeAreas.Push(c)
    if --FreezeDepth > 0
        return
    if !FreezeSent {
        FreezeAreas := []
        return
    }
    SendMessage(0x000B, 1, 0, G)                      ; WM_SETREDRAW true
    whole := false
    for c in FreezeAreas
        whole := whole || !IsObject(c)
    flags := 0x0001 | 0x0004 | 0x0080 | 0x0100        ; RDW_INVALIDATE | ERASE | ALLCHILDREN | UPDATENOW
    if whole
        DllCall("RedrawWindow", "Ptr", G.Hwnd, "Ptr", 0, "Ptr", 0, "UInt", flags)
    else
        for c in FreezeAreas {
            c.GetPos(&x, &y, &w, &h)
            rc := Buffer(16)
            NumPut("Int", x, "Int", y, "Int", x + w, "Int", y + h, rc)
            DllCall("RedrawWindow", "Ptr", G.Hwnd, "Ptr", rc, "Ptr", 0, "UInt", flags)
        }
    FreezeAreas := []
}

; ---- подсказки -------------------------------------------------------------------------------------------
HelpMark(x, y, text) {
    c := G.Add("Text", "x" x " y" y " w18 h18 Center +Border +0x100 c" C_BLUE " Background" C_PANEL, "?")
    AddHelp(c, text)
    return c
}

AddHelp(ctrl, text) {
    HelpMap[ctrl.Hwnd] := text
}

OnMouseMove(wParam, lParam, msg, hwnd) {
    static last := 0
    if hwnd = last
        return
    last := hwnd
    if HelpMap.Has(hwnd) {
        ToolTip(HelpMap[hwnd])                 ; держится, пока мышь над значком
    } else
        ToolTip()
}

; ---- запуск ----------------------------------------------------------------------------------------------
Startup() {
    if SaveEdit.Value = "" || GameEdit.Value = ""
        FindSteam(false)
    if !DataReady() && DirExist(GameEdit.Value)
        SetupData()
    if SaveEdit.Value != "" && FileExist(SaveEdit.Value) && DataReady()
        LoadSave()
}

; Steam: папка игры и самое свежее сохранение. Без force заполняются только пустые поля.
FindSteam(force) {
    StatusText.Value := "Ищу игру в Steam…"
    RunEngine("locate", &out)
    found := ""
    Loop Parse out, "`n", "`r" {
        f := StrSplit(A_LoopField, "`t")
        if f.Length < 2 || f[2] = ""
            continue
        if f[1] = "game" && (force || GameEdit.Value = "") {
            GameEdit.Value := f[2], found .= "игра "
            IniWrite(f[2], INI, "paths", "game")
        }
        if f[1] = "save" && (force || SaveEdit.Value = "") {
            SaveEdit.Value := f[2], found .= "сохранение"
            IniWrite(f[2], INI, "paths", "save")
        }
    }
    StatusText.Value := found != "" ? "Steam: найдено — " found : (force ? "В Steam игра не найдена — укажите пути вручную" : "")
    if force && found != "" && DataReady()
        LoadSave()
}

; ---- раскладка под размер окна ---------------------------------------------------------------------------
OnSize(guiObj, minMax, w, h) {
    if minMax = -1
        return
    Layout(w, h)
}

Layout(w, h) {
    MiriansText.Move(w - 400, 14, 380)
    SaveEdit.Move(128, 48, w - 128 - 420)
    BtnOpen.Move(w - 400, 47), BtnSteam.Move(w - 280, 47), BtnRead.Move(w - 130, 47)
    StatusText.Move(420, 18, Max(100, w - 840))
    Tabs.Move(10, 84, w - 20, h - 94)
    right := Max(380, Round((w - 40) * 0.30))          ; ширина правой карточки на «Предметах»
    left := w - 40 - right - 20                        ; ширина левой части
    rx := 26 + left + 20

    ; навыки: ряды на всю высоту; узел = навык, черта-связка и столбец улучшений справа.
    ; Описание навыка — узкой колонкой, чтобы клеткам хватило ширины; престиж занимает пол-узла.
    sRight := Max(280, Round((w - 40) * 0.17)), sLeft := w - 40 - sRight - 20, sx := 26 + sLeft + 20
    top := 200, rowH := Max(84, (h - 24 - top) // MAX_ROWS)
    labelW := 120, unit := (sLeft - labelW - 10) / (MAX_NODES - 1 + 0.55)
    Loop MAX_ROWS {
        r := A_Index, y := top + (r - 1) * rowH
        RowPanels[r].Move(26, y - 4, sLeft, rowH - 6)
        RowLabels[r].Move(34, y, labelW - 10), RowCounts[r].Move(34, y + 24, labelW - 10)
        x := 26 + labelW
        Loop MAX_NODES {
            n := A_Index
            node := (r <= Rows.Length && n <= Rows[r].nodes.Length) ? Rows[r].nodes[n] : ""
            kids := node ? node.skills.Length - 1 : 0
            nw := Floor((node && node.prestige ? 0.55 : 1) * unit)
            pw := kids ? Round(nw * 0.46) : nw - 6, kw := nw - pw - 12
            SkillTiles[r][n][1].Move(x, y, pw, rowH - 14)
            Connectors[(r - 1) * MAX_NODES + n].Move(x + pw + 2, y + 4, 3, rowH - 22)
            cnt := Max(3, kids), kh := (rowH - 14 - (cnt - 1) * 3) // cnt
            Loop MAX_KIDS
                SkillTiles[r][n][A_Index + 1].Move(x + pw + 7, y + (A_Index - 1) * (kh + 3), kw, kh)
            x += nw
        }
    }
    SkPanel.Move(sx, 122, sRight, h - 140)
    SkillName.Move(sx + 20, 140, sRight - 40, 60), SkillState.Move(sx + 20, 205, sRight - 40)
    SkillDesc.Move(sx + 20, 240, sRight - 40, h - 280)

    ; предметы
    sw := (left - 5 * 6) // 6
    Loop SLOTS.Length
        SlotTiles[A_Index].Move(30 + (A_Index - 1) * (sw + 6), 160, sw, 70)
    SlotCaption.Move(30, 240, left)
    ItemList.Move(30, 264, left, h - 290)
    ItemList.ModifyCol(2, Max(200, left - 24 - 50 - 110 - 250 - 30))
    cardH := Round((h - 140) * 0.66)
    ItPanel.Move(rx, 122, right, cardH)
    ItemTag.Move(rx + 20, 132, right - 40)
    ItemName.Move(rx + 20, 152, right - 150, 60), ItemLevel.Move(rx + right - 130, 148, 110)
    ItemLine.Move(rx + 20, 214, right - 40), ItemDesc.Move(rx + 20, 238, right - 40, 40)
    PlaceEffects()
    GemTitle.Move(rx, 122 + cardH + 10, right)
    GemList.Move(rx, 122 + cardH + 34, right, h - 140 - cardH - 40)
    WorldAct.Move(30, 152, w - 80), RegionList.Move(30, 208, w - 80), CollList.Move(30, 420, w - 80)
    GemList.ModifyCol(1, right - 110)

    ; орки: список слева, карточка орка справа
    oRight := Max(380, Round((w - 40) * 0.30)), oLeft := w - 40 - oRight - 20
    OrcSummary.Move(30, 150, oLeft, 52)
    OrcList.Move(30, 242, oLeft, h - 268)
    OrcInfo.Move(30 + oLeft + 20, 122, oRight, h - 148)

    ; новая игра+ и настройка
    NgSource.Move(30, 156, w - 80)
    OutEdit.Move(280, 224, w - 440), BtnOut.Move(w - 150, 223)
    cw := Max(600, Round((w - 80) * 0.55)), rx := 30 + cw + 20, rw := w - 30 - rx
    LayoutCards(30, 300, cw, h - 24)
    ph := Round((h - 300 - 40) * 0.55)
    DetailPanel.Move(rx, 300, rw, ph), DetailTitle.Move(rx + 20, 312, rw - 40)
    DetailText.Move(rx + 20, 346, rw - 40, ph - 58)
    LogTitle.Move(rx, 300 + ph + 12, rw), NgLog.Move(rx, 300 + ph + 36, rw, h - (300 + ph + 36) - 24)
    SetHelp.Move(30, 160, w - 80), GameEdit.Move(170, 206, w - 330), BtnGame.Move(w - 150, 205)
    SetupLog.Move(30, 296, w - 80), DataState.Move(30, 510, w - 80), ChronHelp.Move(30, 596, w - 80)
    WinRedraw(G)
}

; ---- движок ----------------------------------------------------------------------------------------------
; команда движка: встроенный Python (сборка-папка), engine\sowtool.exe (сборка-файл), иначе (исходники) — python
Engine(&dir) {
    py := APP_DIR "\python\python.exe", exe := APP_DIR "\engine\sowtool.exe"
    if FileExist(py) {
        dir := APP_DIR
        return '"' py '" -m sowtool --data "' DATA_DIR '" '
    }
    if FileExist(exe) {
        dir := APP_DIR
        return '"' exe '" --data "' DATA_DIR '" '
    }
    dir := APP_DIR "\..\engine"
    return 'python -m sowtool --data "' DATA_DIR '" '
}

RunEngine(args, &out) {
    tmp := A_Temp "\sowtool_" A_TickCount ".txt"
    cmd := Engine(&dir) args
    code := RunWait(A_ComSpec ' /c "' cmd ' > "' tmp '" 2>&1"', dir, "Hide")
    out := FileExist(tmp) ? FileRead(tmp, "UTF-8") : ""
    try FileDelete(tmp)
    return code
}

DataReady() => FileExist(DATA_DIR "\game.gamedb") && FileExist(DATA_DIR "\string_ruru.strdb")

UpdateDataState() {
    DataState.Value := DataReady() ? "Данные игры на месте: " DATA_DIR : "Данных игры нет — укажите папку игры и распакуйте."
}

; ---- чтение сохранения -----------------------------------------------------------------------------------
PickSave(*) {
    f := FileSelect(1, SaveDir(SaveEdit.Value), "Сохранение Shadow of War", "Сохранения (*.sav)")
    if f {
        SaveEdit.Value := f
        LoadSave()
    }
}

SaveDir(current) {
    if current != ""
        return current
    steam := RegRead("HKCU\Software\Valve\Steam", "SteamPath", "")
    return steam != "" ? StrReplace(steam, "/", "\") "\userdata" : A_MyDocuments
}

LoadSave() {
    global Rows, Items, Gems, Talion, World
    path := SaveEdit.Value
    if !FileExist(path)
        return MsgBox("Файл не найден:`n" path, "Новая игра+", "Icon!")
    if !DataReady() {
        Tabs.Choose(6)
        return MsgBox("Сначала распакуйте данные игры на вкладке «Настройка».", "Новая игра+", "Icon!")
    }
    IniWrite(path, INI, "paths", "save")
    StatusText.Value := "Читаю сохранение…"
    code := RunEngine('info "' path '" --format tsv', &out)
    StatusText.Value := ""
    if code || !InStr(out, "talion`t")
        return MsgBox(SubStr(RegExReplace(out, "^Ошибка: "), 1, 1500), "Не удалось прочитать сохранение", "Icon!")
    Rows := [], Items := [], Gems := [], warnText := "", World := {act1: "", regions: [], collections: []}
    Loop Parse out, "`n", "`r" {
        if Trim(A_LoopField) = ""
            continue
        f := StrSplit(A_LoopField, "`t")
        if f.Length < 2
            continue
        switch f[1] {
            case "talion":
                Talion := {level: f[2], xp: f[3], xp_next: f[4], mirians: f[5], points: f.Length > 5 ? f[6] : "0"}
            case "row":
                Rows.Push({title: f[2], learned: f[3], total: f[4], nodes: [], last: ""})
            case "skill":
                if !Rows.Length
                    continue
                row := Rows[Rows.Length]
                if f[3] != row.last {
                    row.nodes.Push({skills: [], prestige: false})
                    row.last := f[3]
                }
                if InStr(f[7], "Престиж") = 1
                    row.nodes[row.nodes.Length].prestige := true
                row.nodes[row.nodes.Length].skills.Push(
                    {child: f[4] = "1", learned: f[5] = "1", rank: f[6], name: f[7], key: f[8], text: f.Length > 8 ? f[9] : ""})
            case "item":
                effects := []
                if f.Length > 10
                    for e in StrSplit(f[11], " | ") {
                        p := InStr(e, ":")
                        if p
                            effects.Push({kind: SubStr(e, 1, p - 1), text: SubStr(e, p + 1)})
                    }
                Items.Push({uid: f[2], level: f[3], slot: f[4], rarity: f[5], equipped: f[6] = "1", name: f[7],
                    owner: f[8], line: f.Length > 8 ? f[9] : "", desc: f.Length > 9 ? f[10] : "", effects: effects})
            case "gem":
                Gems.Push({count: f[2], name: f[3]})
            case "world_act1":
                World.act1 := f[2]
            case "world_region":
                World.regions.Push({name: f[2], towers: f[3], ith: f[4], ith_total: f[5], known: f[6], placed: f[7], slots: f[8],
                    tcount: f.Length > 8 ? f[9] : f[3], icount: f.Length > 9 ? f[10] : f[4],
                    gondor: f.Length > 10 ? f[11] : "", shelob: f.Length > 11 ? f[12] : ""})
            case "world_collection":
                World.collections.Push({title: f[2], have: f[3], total: f[4], note: f.Length > 4 ? f[5] : ""})
            case "warning":
                warnText .= "• " f[2] "`n"
        }
    }
    NgSource.Value := "Пройденная игра (сохранение вверху): " path
    if OutEdit.Value = ""
        OutEdit.Value := path
    FillTalion(), FillSkills(), FillItems(), FillGems(), FillWorld()
    LoadOrcs(path)
    UpdatePlan()
    G.GetClientPos(, , &cw, &ch)
    Layout(cw, ch)
    if warnText != ""
        MsgBox("Сохранение прочитано, но:`n`n" warnText, "Новая игра+", "Icon!")
}

FillTalion() {
    LevelText.Value := "Уровень Талиона: " Talion.level "      Очки навыков: " Talion.points
    XpText.Value := Talion.xp " XP  /  " Talion.xp_next " XP"
    XpBar.Value := Talion.xp_next ? Round(100 * Talion.xp / Talion.xp_next) : 0
    MiriansText.Value := Talion.mirians != "" ? Thousands(Talion.mirians) " мириан" : ""
}

Thousands(n) {
    s := String(n), out := ""
    while StrLen(s) > 3 {
        out := " " SubStr(s, -3) out
        s := SubStr(s, 1, -3)
    }
    return s out
}

FillSkills() {
    Loop MAX_ROWS {
        r := A_Index
        row := r <= Rows.Length ? Rows[r] : ""
        RowLabels[r].Value := row ? row.title : ""
        RowCounts[r].Value := row ? row.learned "/" row.total : ""
        Loop MAX_NODES {
            n := A_Index
            node := row && n <= row.nodes.Length ? row.nodes[n] : ""
            con := Connectors[(r - 1) * MAX_NODES + n]
            if node && node.skills.Length > 1 {
                con.Opt("Background" (node.skills[1].learned ? C_BLUE : C_DIM))
                con.Visible := true
            } else
                con.Visible := false
            Loop MAX_KIDS + 1 {
                c := SkillTiles[r][n][A_Index]
                s := node && A_Index <= node.skills.Length ? node.skills[A_Index] : ""
                if !s {
                    c.Visible := false
                    continue
                }
                c.Value := s.name
                c.Opt("Background" (s.learned ? C_ON : C_OFF) " c" (s.learned ? C_TEXT : C_DIM))
                c.Visible := true
            }
        }
    }
}

ShowSkill(r, n, k, *) {
    s := Rows[r].nodes[n].skills[k]
    SkillName.Value := s.name
    state := s.learned ? "Изучено" : "Не изучено"
    SkillState.Value := (s.child ? "Улучшение" : "Навык") " — " state (s.rank > 1 ? " (ранг " s.rank ")" : "")
    SkillDesc.Value := s.text != "" ? s.text : "(описание не найдено: " s.key ")"
}

; ---- предметы --------------------------------------------------------------------------------------------
RarityColor(r) => r = "легендарный" ? C_LGND : r = "эпический" ? C_EPIC : r = "редкий" ? C_RARE : C_TEXT

FillItems() {
    Loop SLOTS.Length {
        i := A_Index, eq := ""
        for it in Items
            if it.slot = SLOTS[i] && it.equipped
                eq := it
        SlotTiles[i].Value := SLOT_TITLES[i] "`n" (eq ? "УР. " eq.level "`n" eq.name : "—")
        SlotTiles[i].Opt("c" (eq ? RarityColor(eq.rarity) : C_DIM))
    }
    SelectSlot(CurrentSlot)
}

SelectSlot(i, *) {
    global CurrentSlot := i
    Freeze()
    Loop SLOTS.Length
        SlotTiles[A_Index].Opt("Background" (A_Index = i ? C_ON : C_OFF))
    ItemList.Opt("-Redraw")
    ItemList.Delete()
    count := 0, sel := 0
    for it in Items {
        if it.slot != SLOTS[i]
            continue
        count++
        row := ItemList.Add(, it.equipped ? "●" : "", it.name, it.level, it.rarity, it.owner, it.uid)
        if it.equipped
            sel := row
    }
    ItemList.Opt("+Redraw")
    SlotCaption.Value := SLOT_TITLES[i] ": " count " шт."
    if sel {
        ItemList.Modify(sel, "Select Focus Vis")
        ShowItem(ItemList.GetText(sel, 6))
    }
    Thaw(SlotCaption, ItemList, ItPanel, OwnerCard, SlotTiles*)
}

ShowItem(uid) {
    global ShownEffects
    for it in Items {
        if it.uid != uid
            continue
        Freeze()
        ItemTag.Value := it.equipped ? "СНАРЯЖЕНО" : ""
        ItemName.Value := it.name
        ItemName.Opt("c" RarityColor(it.rarity))
        ItemLevel.Value := "УР. " it.level
        ItemLine.Value := it.line != "" ? it.line : StrTitle(it.rarity)
        ItemDesc.Value := it.desc
        ItemOwner.Value := it.owner != "" ? "Прежде снаряжением владел`n" it.owner : ""
        ItemOwner.Visible := it.owner != "", OwnerCard.Visible := it.owner != ""
        ShownEffects := Min(MAX_EFFECTS, it.effects.Length)
        Loop MAX_EFFECTS {
            c := EffectTiles[A_Index]
            if A_Index > it.effects.Length {
                c.Visible := false, EffectCards[A_Index].Visible := false
                continue
            }
            e := it.effects[A_Index]
            color := e.kind = "legendary" ? C_LGND : e.kind = "set" ? C_SET : C_TEXT
            c.Value := e.text
            c.Opt("c" color)
            c.Visible := true, EffectCards[A_Index].Visible := true
        }
        PlaceEffects()
        Thaw(ItPanel, OwnerCard)
        return
    }
}

; свойства друг под другом: подложка карточки и текст с отступом 12, высота по длине текста
PlaceEffects() {
    ItPanel.GetPos(&px, &py, &pw, &ph)
    y := py + 160, w := pw - 40, tw := w - 24
    perLine := Max(20, Floor(tw / 7.6))
    Loop MAX_EFFECTS {
        c := EffectTiles[A_Index]
        if A_Index > ShownEffects                      ; не c.Visible: пока окно заморожено, оно врёт
            continue
        lines := Max(1, Ceil(StrLen(c.Value) / perLine))
        th := 19 * lines
        EffectCards[A_Index].Move(px + 20, y, w, th + 16)
        c.Move(px + 32, y + 8, tw, th)
        y += th + 16 + 6
    }
    OwnerCard.Move(px + 20, y + 4, w, 52)
    ItemOwner.Move(px + 32, y + 12, tw, 38)
}

FillWorld() {
    WorldAct.Value := World.act1 = "" ? "" : World.act1 = "1"
        ? "Первый акт пройден."
        : "Первый акт не пройден — при сборке новой игры+ на таком опорном сохранении сюжетный хэдир Минас-Моргула не трогается."
    RegionList.Delete()
    for r in World.regions
        RegionList.Add(, r.name, r.towers "/3" (r.tcount != r.towers ? "  (в игре " r.tcount ")" : ""),
            r.ith "/" r.ith_total (r.icount != r.ith ? "  (в игре " r.icount ")" : ""), r.known, r.placed "/" r.slots,
            r.gondor, r.shelob)
    CollList.Delete()
    for c in World.collections
        CollList.Add(, c.title, c.have, c.total, c.note)
    RegionList.ModifyCol(1, 180), RegionList.ModifyCol(2, 110), RegionList.ModifyCol(3, 110)
    RegionList.ModifyCol(4, 170), RegionList.ModifyCol(5, 140), RegionList.ModifyCol(6, 160), RegionList.ModifyCol(7, 180)
    RegionList.ModifyCol(2, 150), RegionList.ModifyCol(3, 150)
    CollList.ModifyCol(1, 260), CollList.ModifyCol(2, 110), CollList.ModifyCol(3, 90), CollList.ModifyCol(4, "AutoHdr")
}

FillGems() {
    GemList.Delete()
    for g in Gems
        GemList.Add(, g.name, g.count)
}

; ---- орки -----------------------------------------------------------------------------------------------
LoadOrcs(path) {
    global OrcData := []
    weightsText := ""
    StatusText.Value := "Читаю армию Немезиды…"
    code := RunEngine(HistArg() 'orcs "' path '" --format tsv', &out)
    StatusText.Value := ""
    if code {
        OrcSummary.Value := "Не удалось прочитать орков: " SubStr(out, 1, 300)
        return FillOrcs()
    }
    Loop Parse out, "`n", "`r" {
        f := StrSplit(A_LoopField, "`t")
        if f.Length >= 3 && f[1] = "orc_weights" {
            weightsText := "Веса особенностей " f[2] ": " f[3]
            continue
        }
        if f.Length < 22 || f[1] != "orc"
            continue
        shown := false
        for g in ORC_GROUPS
            shown := shown || g = f[2]
        if !shown
            continue
        ; столбцы списка: имя с титулом, уровень, состояние, регион, место, класс, племя, редкость,
        ; счёт, убил Талиона, последний шанс, сбегал, возвращался, гибели, способ переноса, куда, номер
        OrcData.Push({group: f[2], num: f[3], name: Trim(f[4] " " f[5]),
            cells: [Trim(f[4] " " f[5]), f[6], f[7], f[8], f[9], f[10], f[11], f[12], f[13], f[14], f[15], f[16],
                f[17], f[18], f[19], f[20], f[3]],
            info: StrReplace(f[22], " ¶ ", "`r`n")})
    }
    counts := Map()
    for o in OrcData
        counts[o.group] := (counts.Has(o.group) ? counts[o.group] : 0) + 1
    s := "Всего орков: " OrcData.Length
    for g in ORC_GROUPS
        if counts.Has(g)
            s .= "   •   " g ": " counts[g]
    OrcSummary.Value := s "`n" weightsText
    FillOrcs()
}

; группы списка (сворачиваемые) — через сообщения ListView: LVM_ENABLEGROUPVIEW, LVM_INSERTGROUP, LVM_SETITEM
FillOrcs() {
    static made := false
    q := Trim(OrcSearch.Value)
    OrcList.Opt("-Redraw")
    OrcList.Delete()
    SendMessage(0x10A0, 0, 0, OrcList)                 ; LVM_REMOVEALLGROUPS
    SendMessage(0x109D, 1, 0, OrcList)                 ; LVM_ENABLEGROUPVIEW
    counts := Map()
    for o in OrcData
        if q = "" || InStr(o.name, q)
            counts[o.group] := (counts.Has(o.group) ? counts[o.group] : 0) + 1
    for i, g in ORC_GROUPS
        if counts.Has(g)
            OrcGroup(i, g " (" counts[g] ")", i > 1)
    for o in OrcData {
        if q != "" && !InStr(o.name, q)
            continue
        row := OrcList.Add(, o.cells*)
        gid := 0
        for i, g in ORC_GROUPS
            if g = o.group
                gid := i
        item := Buffer(88, 0)                          ; LVITEMW: mask, iItem, …, iGroupId (смещение 52 в x64)
        NumPut("UInt", 0x100, item, 0), NumPut("Int", row - 1, item, 4), NumPut("Int", gid, item, 52)
        SendMessage(0x104C, 0, item, OrcList)          ; LVM_SETITEMW
    }
    if !made {
        widths := [230, 44, 60, 110, 90, 90, 130, 100, 54, 60, 74, 60, 60, 60, 170, 100, 50]
        for i, wd in widths
            OrcList.ModifyCol(i, wd)
        made := true
    }
    OrcList.Opt("+Redraw")
}

OrcGroup(id, title, collapsed) {
    hdr := Buffer(StrLen(title) * 2 + 2)
    StrPut(title, hdr, "UTF-16")
    g := Buffer(152, 0)                                ; LVGROUP (x64)
    NumPut("UInt", 152, g, 0)
    NumPut("UInt", 0x1 | 0x4 | 0x10, g, 4)             ; LVGF_HEADER | LVGF_STATE | LVGF_GROUPID
    NumPut("Ptr", hdr.Ptr, g, 8)
    NumPut("Int", id, g, 36)
    NumPut("UInt", 0x9, g, 40)                         ; stateMask: COLLAPSIBLE | COLLAPSED
    NumPut("UInt", 0x8 | (collapsed ? 0x1 : 0), g, 44)
    SendMessage(0x1091, -1, g, OrcList)                ; LVM_INSERTGROUP
}

ShowOrc(num) {
    for o in OrcData
        if o.num = num {
            OrcInfo.Value := o.info
            return
        }
}

; ---- карточки настроек новой игры+ -----------------------------------------------------------------------
; карточка: подложка, квадратик-переключатель, заголовок и строка «что будет сейчас»; щелчок по заголовку или
; строке только выбирает карточку (подробности — в панели справа), переключает только квадратик
AddCard(group, key, title, def, detail) {
    v := IniRead(INI, "ngplus", key, def ? "1" : "0")
    panel := G.Add("Text", "x0 y0 w10 h10 Background" C_CARD)     ; без щелчка: не перехватывает квадратик
    box := G.Add("CheckBox", "x0 y0 w20 h20 Background" C_CARD (v = "1" ? " Checked" : ""))
    box.OnEvent("Click", CardBoxClick.Bind(key))
    G.SetFont("s10 bold c" C_TEXT)
    head := G.Add("Text", "x0 y0 w10 h20 BackgroundTrans", title)
    head.OnEvent("Click", SelectCard.Bind(key))
    G.SetFont("s9 norm c" C_DIM)
    sub := G.Add("Text", "x0 y0 w10 h18 BackgroundTrans", "")
    sub.OnEvent("Click", SelectCard.Bind(key))
    G.SetFont("s10 norm c" C_TEXT)
    CARDS.Push({group: group, key: key, title: title, detail: detail, box: box, panel: panel, head: head, sub: sub})
}

Card(key) {
    for c in CARDS
        if c.key = key
            return c
}

CardValue(key) => Card(key).box.Value

; группы сверху вниз, под карточкой двадцатки — её списки, внизу кнопка «Собрать». Не влезает в окно — ползунок
; справа и колесо мыши; вышедшее за видимую часть скрывается
LayoutCards(x := 0, y := 0, w := 0, bottom := 0) {
    global CardScroll, CardView
    if bottom
        CardView := [x, y, w, bottom]
    x := CardView[1], top := CardView[2], w := CardView[3] - 30, bottom := CardView[4]
    place := []                                     ; [элемент, x, y от начала списка, ширина, высота]
    yy := 0
    for grp in CARD_GROUPS {
        place.Push([GroupHeads[grp], x, yy, w, 22])
        yy += 26
        for c in CARDS {
            if c.group != grp
                continue
            place.Push([c.panel, x, yy, w, 42], [c.box, x + 12, yy + 3, 20, 20], [c.head, x + 38, yy + 3, w - 50, 20],
                [c.sub, x + 38, yy + 22, w - 50, 18])
            yy += 46
            if c.key = "twenty" {
                place.Push([TwLevelLabel, x + 38, yy + 4, 70, 22], [TwLevel, x + 108, yy, 190, 26],
                    [TwWeakLabel, x + 316, yy + 4, 80, 22], [TwWeak, x + 396, yy, Min(230, w - 400), 26],
                    [TwHistLabel, x + 38, yy + 38, 70, 22], [TwHist, x + 108, yy + 34, 250, 26])
                yy += 68
            }
        }
        yy += 8
    }
    place.Push([BtnBuild, x, yy, 300, 36])
    yy += 40
    over := Max(0, yy - (bottom - top))
    CardScroll := Max(0, Min(CardScroll, over))
    for p in place {
        cy := top + p[3] - CardScroll
        p[1].Move(p[2], cy, p[4], p[5])
        p[1].Visible := cy >= top && cy + p[5] <= bottom
    }
    CardScrollBar.Opt("Range0-" over)
    CardScrollBar.Value := CardScroll
    CardScrollBar.Move(x + w + 6, top, 24, bottom - top)
    CardScrollBar.Visible := over > 0
}

CardScrollMove(ctl, *) {
    global CardScroll := ctl.Value
    LayoutCards()
}

; колесо мыши над карточками новой игры+
OnCardWheel(wParam, lParam, msg, hwnd) {
    global CardScroll
    if Tabs.Value != 5
        return
    CoordMode("Mouse", "Client")
    MouseGetPos(&mx, &my, &win)
    if win != G.Hwnd || mx < CardView[1] || mx > CardView[1] + CardView[3] || my < CardView[2] || my > CardView[4]
        return
    d := (wParam >> 16) & 0xFFFF
    d := d > 0x7FFF ? d - 0x10000 : d
    CardScroll -= d // 120 * 60
    LayoutCards()
    return 0
}

IniChoice(key, list, def := "") {
    v := IniRead(INI, "ngplus", key, def != "" ? def : list[1][1])
    for k in [v, def]
        for i, it in list
            if it[1] = k
                return i
    return 1
}

Labels(list) {
    out := []
    for it in list
        out.Push(it[2])
    return out
}

CardBoxClick(key, *) {
    UpdateCardStates()
    SelectCard(key)
}

; списки двадцатки — только с её карточкой
; память новой игры+ (движок: --history) — меняет счёт орков: и рекомендации, и план
HistArg() => "--history " TW_HISTORY[TwHist.Value][1] " "
ChangeHistory() {
    IniWrite(TW_HISTORY[TwHist.Value][1], INI, "ngplus", "twenty_history")
    if SaveEdit.Value != "" && FileExist(SaveEdit.Value) && DataReady()
        LoadOrcs(SaveEdit.Value), UpdatePlan()
    SelectCard("twenty")
}

UpdateCardStates() {
    TwLevel.Enabled := CardValue("twenty"), TwWeak.Enabled := CardValue("twenty"), TwHist.Enabled := CardValue("twenty")
}

SelectCard(key, *) {
    global SelectedCard := key
    areas := []
    for c in CARDS                                   ; до заморозки: пока окно заморожено, Visible врёт
        if c.panel.Visible
            areas.Push(c.panel, c.box)
    Freeze()
    for c in CARDS {
        color := c.key = key ? C_ON : C_CARD
        c.panel.Opt("Background" color), c.box.Opt("Background" color)
    }
    c := Card(key)
    DetailTitle.Value := c.title
    DetailText.Value := (c.sub.Value != "" ? "Сейчас: " c.sub.Value "`r`n`r`n" : "") c.detail
    areas.Push(DetailPanel)
    Thaw(areas*)
}

; строки «что будет сейчас» по выбранному началу и пройденной игре (движок: plan)
; строка карточки врагов — для выбранного «Сколько»
ShowTwentyPlan() {
    k := TW_COUNTS[TwLevel.Value][1]
    Card("twenty").sub.Value := TwPlan.Has(k) ? TwPlan[k] : ""
}

UpdatePlan() {
    base := BasePath(), src := SaveEdit.Value
    global TwPlan := Map()
    for c in CARDS
        c.sub.Value := ""
    UpdateCardStates()
    if !FileExist(base) || !FileExist(src) || !DataReady() {
        Card("start").sub.Value := "откройте пройденную игру вверху — здесь появятся цифры"
        return SelectCard(SelectedCard)
    }
    RunEngine(HistArg() 'plan --base "' base '" --source "' src '"', &out)
    act1 := true, level := ""
    Loop Parse out, "`n", "`r" {
        f := StrSplit(A_LoopField, "`t")
        switch f.Length ? f[1] : "" {
            case "plan_base":
                act1 := f[2] = "1"
            case "plan_level":
                level := f[2]
                Card("start").sub.Value := "В пройденной игре у Талиона уровень " f[2] "; станет " f[3]
                    . (act1 ? " — средний уровень капитанов Нурна минус 2" : " — начало после пролога")
            case "plan_towers":
                Card("towers").sub.Value := "захваченных хэдиров перенесётся: " f[2]
                    . (act1 ? "" : " (в Минас-Моргуле — кроме сюжетного)")
            case "plan_collect":
                n := f.Length > 2 ? f[3] : ""
                what := Map("ithildin", "слов итильдина", "gondor", "гондорских артефактов", "shelob", "воспоминаний")[f[2]]
                Card(f[2]).sub.Value := "перенесётся " n " " what
            case "plan_clean":
                Card("clean").sub.Value := "уберётся предметов: " f[2] " из " f[3]
            case "plan_twenty":                  ; <сколько> <достойных> <поставлено> <куда>
                TwPlan[f[2]] := f[3] = "0" ? "в пройденной игре нет орков для переноса"
                    : "вернётся " f[4] " из " f[3] " достойных: " (f.Length > 4 ? f[5] : "")
                    . (act1 ? " (на втором акте — без Кирит-Унгола)" : "")
        }
    }
    ShowTwentyPlan()
    SelectCard(SelectedCard)
}

; ---- новая игра+ -----------------------------------------------------------------------------------------
PickOut(*) {
    f := FileSelect("S16", SaveDir(OutEdit.Value != "" ? OutEdit.Value : SaveEdit.Value), "Куда записать", "Сохранения (*.sav)")
    if f
        OutEdit.Value := f
}

; опорное сохранение: одно из двух готовых в папке bases
BasePath() => APP_DIR "\bases\" BASES[BaseChoice.Value][2]

BuildNGPlus(*) {
    base := BasePath(), src := SaveEdit.Value, out := OutEdit.Value
    if !FileExist(base) || !FileExist(src) || out = ""
        return MsgBox("Нужны: сохранение вверху (пройденная игра) и файл, куда записать.`n"
            . "Если опорное сохранение не найдено — проверьте папку bases рядом с программой.", "Новая игра+", "Icon!")
    if !DataReady()
        return MsgBox("Сначала распакуйте данные игры на вкладке «Настройка».", "Новая игра+", "Icon!")
    if !RegExMatch(out, "i)_ShadowOfWar\.sav$")
        if MsgBox("Имя файла не похоже на сохранение игры (<номер или имя компьютера>_ShadowOfWar.sav). Игра его не увидит. Продолжить?",
            "Новая игра+", "YesNo Icon?") != "Yes"
            return
    IniWrite(BaseChoice.Value, INI, "paths", "base_choice"), IniWrite(out, INI, "paths", "out")
    for c in CARDS
        IniWrite(c.box.Value, INI, "ngplus", c.key)
    note := ""
    if FileExist(out) && BackupBox.Value {
        bak := out "." FormatTime(, "yyyyMMdd-HHmmss") ".bak"
        FileCopy(out, bak)
        note .= "Копия: " bak "`r`n"
    }
    ; источник и цель могут быть одним файлом: движок читает источник из временной копии
    tmpSrc := A_Temp "\sowngp_" A_TickCount "_" RegExReplace(src, ".*\\")
    FileCopy(src, tmpSrc, true)
    NgLog.Value := note "Собираю…"
    opts := Map("towers", "--towers", "ithildin", "--ithildin", "gondor", "--gondor", "shelob", "--shelob",
        "start", "--start-level", "clean", "--clean-gear", "twenty", "--twenty")
    args := ""
    for c in CARDS
        if c.box.Value
            args .= " " opts[c.key]
    IniWrite(TW_COUNTS[TwLevel.Value][1], INI, "ngplus", "twenty_count")
    IniWrite(TW_WEAK[TwWeak.Value][1], INI, "ngplus", "twenty_weak")
    IniWrite(TW_HISTORY[TwHist.Value][1], INI, "ngplus", "twenty_history")
    if CardValue("twenty")
        args .= " --twenty-count " TW_COUNTS[TwLevel.Value][1] " --weak " TW_WEAK[TwWeak.Value][1]
    code := RunEngine(HistArg() 'ngplus --base "' base '" --source "' tmpSrc '" --out "' out '"' args, &res)
    if !code {         ; копия пройденной игры — летописи (узнавать «наших» орков, даже если источник потом перезаписан)
        DirCreate(CHRON_DIR "\источник")
        try FileDelete(CHRON_DIR "\источник\*.sav")
        try FileCopy(tmpSrc, CHRON_DIR "\источник\" RegExReplace(src, ".*\\"), true)
    }
    try FileDelete(tmpSrc)
    NgLog.Value := note StrReplace(res, "`n", "`r`n") (code ? "`r`nНичего не записано." : "`r`nГотово.")
    if !code {
        SaveEdit.Value := out
        LoadSave()
    }
}

; ---- настройка -------------------------------------------------------------------------------------------
PickGame(*) {
    d := DirSelect("*" GameEdit.Value, 0, "Папка Shadow of War")
    if d
        GameEdit.Value := d
}

; ---- летопись --------------------------------------------------------------------------------------------

ToggleChronicle() {
    global ChronPid
    if ChronPid && ProcessExist(ChronPid)
        return StopChronicle()
    if !DataReady()
        return MsgBox("Сначала распакуйте данные игры.", "Летопись", "Icon!")
    ; --parent: летопись сама остановится, если окна не станет (упало, снято в диспетчере)
    args := 'chronicle --out "' CHRON_DIR '" --parent ' DllCall("GetCurrentProcessId")
    if OutEdit.Value != "" && FileExist(OutEdit.Value)
        args .= ' --save "' OutEdit.Value '"'
    ; пройденная игра — копия, оставленная последней сборкой; иначе поле вверху, если это не тот же файл, за которым
    ; следим (тогда «нашими» оказались бы все)
    src := ""
    Loop Files CHRON_DIR "\источник\*.sav"
        src := A_LoopFileFullPath
    if src = "" && SaveEdit.Value != "" && FileExist(SaveEdit.Value) && SaveEdit.Value != OutEdit.Value
        src := SaveEdit.Value
    if src != ""
        args .= ' --source "' src '"'
    cmd := Engine(&dir) args
    Run(cmd, dir, "Hide", &pid)
    ChronPid := pid
    BtnChron.Text := "Остановить летопись"
    ChronState.Value := "Летопись идёт: " CHRON_DIR "\летопись.txt"
}

StopChronicle() {
    global ChronPid
    if ChronPid && ProcessExist(ChronPid)
        ProcessClose(ChronPid)
    ChronPid := 0
    try BtnChron.Text := "Включить летопись"
    try ChronState.Value := "Летопись выключена."
}

SetupData() {
    if !DirExist(GameEdit.Value)
        return MsgBox("Укажите папку игры.", "Новая игра+", "Icon!")
    IniWrite(GameEdit.Value, INI, "paths", "game")
    SetupLog.Value := "Распаковываю…"
    StatusText.Value := "Распаковываю данные игры (около минуты)…"
    code := RunEngine('setup --game "' GameEdit.Value '"', &res)
    StatusText.Value := ""
    SetupLog.Value := StrReplace(res, "`n", "`r`n") (code ? "`r`nОШИБКА (код " code ")" : "`r`nГотово.")
    UpdateDataState()
}
