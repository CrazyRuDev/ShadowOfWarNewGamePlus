; Оверлей очереди Немезиды поверх игры (левый верхний угол).
; Данные пишет слежение за сохранениями (watch_saves.bat) в "game files\история\оверлей.txt" после каждой записи
; сохранения игрой; между записями оверлей сам отсчитывает время. Мышь проходит сквозь оверлей.
; F8 — скрыть/показать, Ctrl+F8 — закрыть. Игра должна быть в оконном режиме без рамки (поверх полноэкранного
; режима Windows ничего не рисует).
#Requires AutoHotkey v2.0
#SingleInstance Force

global DATA_FILE := A_ScriptDir "\..\game files\история\оверлей.txt"
global LastStamp := ""
global SavedMs := 0, SaveName := "", TalionLevel := "", Mirians := ""
global QueueRows := []      ; [{ms, event, descr, region, orc}]
global ChangeRows := []     ; [{time, text}]
global Shown := true

global Ov := Gui("+AlwaysOnTop -Caption +ToolWindow +E0x20 +Owner")
Ov.BackColor := "0E1116"
Ov.MarginX := 12, Ov.MarginY := 8
Ov.SetFont("s10 cE6E6E6", "Consolas")
global Body := Ov.Add("Text", "w640 r6", "Жду данные от слежения за сохранениями…")
Ov.Show("x8 y8 NoActivate AutoSize")
WinSetTransparent(220, Ov)

SetTimer(Tick, 500)
Tick()

F8:: {
    global Shown
    Shown := !Shown
    if Shown
        Ov.Show("NoActivate")
    else
        Ov.Hide()
}
^F8::ExitApp()

NowMs() => DateDiff(A_NowUTC, "19700101000000", "Seconds") * 1000 + A_MSec

Fmt(ms) {
    s := Max(ms, 0) // 1000
    if s >= 3600
        return Format("{}:{:02}:{:02}", s // 3600, Mod(s // 60, 60), Mod(s, 60))
    return Format("{}:{:02}", s // 60, Mod(s, 60))
}

ReadData() {
    global LastStamp, SavedMs, SaveName, TalionLevel, Mirians, QueueRows, ChangeRows
    if !FileExist(DATA_FILE)
        return false
    stamp := FileGetTime(DATA_FILE, "M") FileGetSize(DATA_FILE)
    if stamp = LastStamp
        return true
    try text := FileRead(DATA_FILE, "UTF-8")
    catch
        return true                      ; файл как раз заменяют — прочитаем на следующем шаге
    LastStamp := stamp
    QueueRows := [], ChangeRows := []
    Loop Parse text, "`n", "`r" {
        f := StrSplit(A_LoopField, "`t")
        if f.Length < 2
            continue
        switch f[1] {
            case "saved":
                SavedMs := Integer(f[2]), SaveName := f.Length > 2 ? f[3] : ""
                TalionLevel := f.Length > 3 ? f[4] : "", Mirians := f.Length > 4 ? f[5] : ""
            case "event":
                QueueRows.Push({ms: Integer(f[2]), event: f[3], descr: f.Length > 3 ? f[4] : "",
                    region: f.Length > 4 ? f[5] : "", orc: f.Length > 5 ? f[6] : ""})
            case "change":
                ChangeRows.Push({time: f[2], text: f.Length > 2 ? f[3] : ""})
        }
    }
    return true
}

Tick() {
    if !ReadData() {
        Body.Value := "Нет данных: запустите watch_saves.bat (слежение за сохранениями)."
        Ov.Show("NoActivate AutoSize")
        return
    }
    if !Shown
        return
    since := NowMs() - SavedMs
    out := Format("ОЧЕРЕДЬ НЕМЕЗИДЫ   (сохранение {} назад, Талион ур. {})`n", Fmt(since), TalionLevel)
    out .= "время игровое: идёт, только пока играете; ≈ — отсчёт после последней записи`n"
    out .= "──────────────────────────────────────────────────────────────`n"
    if QueueRows.Length = 0
        out .= "  (очередь пуста)`n"
    for r in QueueRows {
        left := r.ms - since
        mark := left <= 0 ? "сейчас/ждёт" : "≈ " Fmt(left)
        what := r.descr != "" ? r.descr : r.event
        out .= Format("  {:-12} {:-34} {:-13} {}`n", mark, SubStr(what, 1, 34), r.region, r.orc)
        if r.descr != ""
            out .= Format("  {:-12} {}`n", "", r.event)
    }
    if ChangeRows.Length {
        out .= "──────────────────────────────────────────────────────────────`n"
        out .= "ИЗМЕНЕНИЯ ОЧЕРЕДИ`n"
        i := ChangeRows.Length
        while i >= 1 && ChangeRows.Length - i < 8 {
            out .= "  " ChangeRows[i].time "  " ChangeRows[i].text "`n"
            i -= 1
        }
    }
    if since > 120000
        out .= "`n(сохранение не менялось больше 2 минут — игра в меню или слежение остановлено)"
    if Body.Value != out {
        lines := StrSplit(RTrim(out, "`n"), "`n").Length
        Body.Move(, , 640, lines * 17 + 4)
        Body.Value := out
        Ov.Show("NoActivate AutoSize")
    }
}
