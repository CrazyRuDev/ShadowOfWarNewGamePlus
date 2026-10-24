# Lists the files inside every Shadow of War .arch06 archive (LTAR v4).
# Reads only the archive headers, changes nothing.
# Output: sow_archlist.txt on the desktop, one line per file: archive <tab> path <tab> unpacked size.
param([string]$GameDir = 'D:\SteamLibrary\steamapps\common\ShadowOfWar')

$out = Join-Path ([Environment]::GetFolderPath('Desktop')) 'sow_archlist.txt'
$lines = New-Object System.Collections.Generic.List[string]

foreach ($arch in Get-ChildItem -LiteralPath $GameDir -Recurse -Filter *.arch06) {
    $fs = [IO.File]::OpenRead($arch.FullName)
    try {
        $br = New-Object IO.BinaryReader($fs)
        $magic = [Text.Encoding]::ASCII.GetString($br.ReadBytes(4))
        if ($magic -ne 'LTAR') { $lines.Add("$($arch.Name)`t<not LTAR>`t0"); continue }
        $null = $br.ReadUInt32()
        $nameSize = $br.ReadUInt32(); $folderCount = $br.ReadUInt32(); $fileCount = $br.ReadUInt32()
        $fs.Position = 0x30
        $names = $br.ReadBytes($nameSize)
        $files = New-Object System.Collections.Generic.List[object]
        for ($i = 0; $i -lt $fileCount; $i++) {
            $nameOff = $br.ReadUInt32(); $null = $br.ReadUInt64(); $null = $br.ReadUInt64()
            $size = $br.ReadUInt64(); $null = $br.ReadUInt16()
            $files.Add(@($nameOff, $size))
        }
        $getName = {
            param($o)
            $e = [Array]::IndexOf($names, [byte]0, [int]$o)
            [Text.Encoding]::ASCII.GetString($names, $o, $e - $o)
        }
        $fileIndex = 0
        for ($i = 0; $i -lt $folderCount; $i++) {
            $folderName = & $getName $br.ReadUInt32()
            $null = $br.ReadUInt32(); $null = $br.ReadUInt32()
            $n = $br.ReadUInt32()
            for ($k = 0; $k -lt $n -and $fileIndex -lt $fileCount; $k++, $fileIndex++) {
                $f = $files[$fileIndex]
                $path = if ($folderName) { "$folderName\" + (& $getName $f[0]) } else { & $getName $f[0] }
                $lines.Add("$($arch.Name)`t$path`t$($f[1])")
            }
        }
    } finally { $fs.Close() }
}

[IO.File]::WriteAllLines($out, $lines)
"Done: $($lines.Count) files -> $out"
