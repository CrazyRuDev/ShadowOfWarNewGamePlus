# Copies selected files out of Shadow of War .arch06 archives as they are stored (still compressed).
# Reads the archives, changes nothing. Output: folder sow_extract on the desktop with
#   <archive>__<path with \ replaced by _>.raw   - the stored bytes of the file
#   manifest.txt                                 - archive, path, stored size, unpacked size
param([string]$GameDir = 'D:\SteamLibrary\steamapps\common\ShadowOfWar')

$wanted = @(
    @('Patch_04.arch06', 'database\game\game.gamedb'),
    @('hotchunk.arch06', 'database\game\game.gamedb'),
    @('Patch_02.arch06', 'database\string\ruru\string.strdb'),
    @('hotchunk.arch06', 'database\string\ruru\string.strdb'),
    @('Patch_02.arch06', 'database\string\enus\string.strdb')
)

$outDir = Join-Path ([Environment]::GetFolderPath('Desktop')) 'sow_extract'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$manifest = New-Object System.Collections.Generic.List[string]

foreach ($archName in ($wanted | ForEach-Object { $_[0] } | Sort-Object -Unique)) {
    $arch = Get-ChildItem -LiteralPath $GameDir -Recurse -Filter $archName | Select-Object -First 1
    if (-not $arch) { Write-Warning "Not found: $archName"; continue }
    $paths = $wanted | Where-Object { $_[0] -eq $archName } | ForEach-Object { $_[1] }

    $fs = [IO.File]::OpenRead($arch.FullName)
    try {
        $br = New-Object IO.BinaryReader($fs)
        $null = $br.ReadBytes(8)
        $nameSize = $br.ReadUInt32(); $folderCount = $br.ReadUInt32(); $fileCount = $br.ReadUInt32()
        $fs.Position = 0x30
        $names = $br.ReadBytes($nameSize)
        $getName = {
            param($o)
            $e = [Array]::IndexOf($names, [byte]0, [int]$o)
            [Text.Encoding]::ASCII.GetString($names, $o, $e - $o)
        }
        $files = New-Object System.Collections.Generic.List[object]
        for ($i = 0; $i -lt $fileCount; $i++) {
            $files.Add(@($br.ReadUInt32(), $br.ReadUInt64(), $br.ReadUInt64(), $br.ReadUInt64()))
            $null = $br.ReadUInt16()
        }
        $fileIndex = 0
        $found = @()
        for ($i = 0; $i -lt $folderCount; $i++) {
            $folderName = & $getName $br.ReadUInt32()
            $null = $br.ReadUInt32(); $null = $br.ReadUInt32()
            $n = $br.ReadUInt32()
            for ($k = 0; $k -lt $n -and $fileIndex -lt $fileCount; $k++, $fileIndex++) {
                $f = $files[$fileIndex]
                $path = if ($folderName) { "$folderName\" + (& $getName $f[0]) } else { & $getName $f[0] }
                if ($paths -contains $path) { $found += ,@($path, $f) }
            }
        }
        foreach ($item in $found) {
            $path = $item[0]; $f = $item[1]
            $fs.Position = [int64]$f[1]
            $data = $br.ReadBytes([int]$f[2])
            $outName = "$($arch.BaseName)__" + ($path -replace '\\', '_') + '.raw'
            [IO.File]::WriteAllBytes((Join-Path $outDir $outName), $data)
            $manifest.Add("$archName`t$path`t$($f[2])`t$($f[3])")
            "OK  $archName  $path  ($([math]::Round($f[2]/1MB,1)) MB)"
        }
        foreach ($p in $paths) {
            if (-not ($found | Where-Object { $_[0] -eq $p })) { Write-Warning "Not in ${archName}: $p" }
        }
    } finally { $fs.Close() }
}

[IO.File]::WriteAllLines((Join-Path $outDir 'manifest.txt'), $manifest)
Compress-Archive -Path (Join-Path $outDir '*') -DestinationPath "$outDir.zip" -Force
"Done -> $outDir.zip"
