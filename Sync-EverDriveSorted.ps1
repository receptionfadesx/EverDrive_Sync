<#
.SYNOPSIS
    EverDrive GB X7 - Smart SD Card Manager
.DESCRIPTION
    A powerful utility to sync, organize, and manage Game Boy and Game Boy Color ROMs 
    for the EverDrive GB X7. Includes intelligent alphabetical sorting, 1G1R filtering, 
    automatic series grouping, and save file management.
.NOTES
    Safety checks are built-in to prevent accidental modification of system drives.
#>
#Requires -Version 5.1

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# Config Path
$configPath = Join-Path $env:USERPROFILE ".everdrive_sync_config.json"

# Load config if exists
$lastSource = ""
$lastDest = ""
$lastHacks = ""
$lastGbcSysPayload = ""
if (Test-Path -LiteralPath $configPath) {
    try {
        $config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
        $lastSource = $config.Source
        $lastDest = $config.Dest
        if ($config.Hacks) { $lastHacks = $config.Hacks }
        if ($config.GbcSysPayload) { $lastGbcSysPayload = $config.GbcSysPayload }
    }
    catch {}
}

# Create the Main Form
$form = New-Object System.Windows.Forms.Form
$form.Text = "Sync Tool for EverDrive GB X7"
$form.Size = New-Object System.Drawing.Size(540, 760)
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false

# Source Label
$lblSource = New-Object System.Windows.Forms.Label
$lblSource.Location = New-Object System.Drawing.Point(15, 20)
$lblSource.Size = New-Object System.Drawing.Size(60, 20)
$lblSource.Text = "Source:"
$form.Controls.Add($lblSource)

# Source TextBox
$txtSource = New-Object System.Windows.Forms.TextBox
$txtSource.Location = New-Object System.Drawing.Point(85, 17)
$txtSource.Size = New-Object System.Drawing.Size(305, 20)
$txtSource.Text = $lastSource
$form.Controls.Add($txtSource)

# Source Browse Button
$btnSource = New-Object System.Windows.Forms.Button
$btnSource.Location = New-Object System.Drawing.Point(400, 15)
$btnSource.Size = New-Object System.Drawing.Size(85, 24)
$btnSource.Text = "Browse..."
$btnSource.Add_Click({
        $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
        $dialog.Description = "Select Source Folder (Your ROMs)"
        if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
            $txtSource.Text = $dialog.SelectedPath
        }
    })
$form.Controls.Add($btnSource)

# Hacks Source Label
$lblHacks = New-Object System.Windows.Forms.Label
$lblHacks.Location = New-Object System.Drawing.Point(15, 60)
$lblHacks.Size = New-Object System.Drawing.Size(70, 20)
$lblHacks.Text = "ROM Hacks:"
$form.Controls.Add($lblHacks)

# Hacks TextBox
$txtHacks = New-Object System.Windows.Forms.TextBox
$txtHacks.Location = New-Object System.Drawing.Point(85, 57)
$txtHacks.Size = New-Object System.Drawing.Size(305, 20)
$txtHacks.Text = $lastHacks
$form.Controls.Add($txtHacks)

# Hacks Browse Button
$btnHacks = New-Object System.Windows.Forms.Button
$btnHacks.Location = New-Object System.Drawing.Point(400, 55)
$btnHacks.Size = New-Object System.Drawing.Size(85, 24)
$btnHacks.Text = "Browse..."
$btnHacks.Add_Click({
        $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
        $dialog.Description = "Select ROM Hacks Folder (Optional)"
        if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
            $txtHacks.Text = $dialog.SelectedPath
        }
    })
$form.Controls.Add($btnHacks)

# GBCSYS Label
$lblGbcSysPayload = New-Object System.Windows.Forms.Label
$lblGbcSysPayload.Location = New-Object System.Drawing.Point(15, 100)
$lblGbcSysPayload.Size = New-Object System.Drawing.Size(70, 20)
$lblGbcSysPayload.Text = "GBCSYS:"
$form.Controls.Add($lblGbcSysPayload)

# GBCSYS Payload TextBox
$txtGbcSysPayload = New-Object System.Windows.Forms.TextBox
$txtGbcSysPayload.Location = New-Object System.Drawing.Point(85, 97)
$txtGbcSysPayload.Size = New-Object System.Drawing.Size(305, 20)
$txtGbcSysPayload.Text = $lastGbcSysPayload
$form.Controls.Add($txtGbcSysPayload)

# GBCSYS Payload Browse Button
$btnGbcSysPayload = New-Object System.Windows.Forms.Button
$btnGbcSysPayload.Location = New-Object System.Drawing.Point(400, 95)
$btnGbcSysPayload.Size = New-Object System.Drawing.Size(85, 24)
$btnGbcSysPayload.Text = "Browse..."
$btnGbcSysPayload.Add_Click({
        $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
        $dialog.Description = "Select GBCSYS Folder (Optional)"
        if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
            $txtGbcSysPayload.Text = $dialog.SelectedPath
        }
    })
$form.Controls.Add($btnGbcSysPayload)

# Destination Label
$lblDest = New-Object System.Windows.Forms.Label
$lblDest.Location = New-Object System.Drawing.Point(15, 140)
$lblDest.Size = New-Object System.Drawing.Size(70, 20)
$lblDest.Text = "SD Card:"
$form.Controls.Add($lblDest)

# Destination TextBox
$txtDest = New-Object System.Windows.Forms.TextBox
$txtDest.Location = New-Object System.Drawing.Point(85, 137)
$txtDest.Size = New-Object System.Drawing.Size(305, 20)
$txtDest.Text = $lastDest
$form.Controls.Add($txtDest)

# Destination Browse Button
$btnDest = New-Object System.Windows.Forms.Button
$btnDest.Location = New-Object System.Drawing.Point(400, 135)
$btnDest.Size = New-Object System.Drawing.Size(85, 24)
$btnDest.Text = "Browse..."
$btnDest.Add_Click({
        $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
        $dialog.Description = "Select Destination Folder (Your SD Card)"
        if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
            $txtDest.Text = $dialog.SelectedPath
        }
    })
$form.Controls.Add($btnDest)
# Checkbox: Smart Reorganize
$chkGroup = New-Object System.Windows.Forms.CheckBox
$chkGroup.Location = New-Object System.Drawing.Point(85, 170)
$chkGroup.Size = New-Object System.Drawing.Size(400, 20)
$chkGroup.Text = "Auto-Reorganize (Places files onto the SD card in alphabetical order)"
$chkGroup.Checked = $true
$chkGroup.Add_CheckedChanged({
        $chkTypeFolders.Enabled = $chkGroup.Checked
        $chkSeriesFolders.Enabled = $chkGroup.Checked
        $chkAZFolders.Enabled = $chkGroup.Checked
    })
$form.Controls.Add($chkGroup)

# Checkbox: System Type Folders
$chkTypeFolders = New-Object System.Windows.Forms.CheckBox
$chkTypeFolders.Location = New-Object System.Drawing.Point(105, 195)
$chkTypeFolders.Size = New-Object System.Drawing.Size(400, 20)
$chkTypeFolders.Text = "Separate games into system folders (GB/GBC)"
$chkTypeFolders.Checked = $true
$form.Controls.Add($chkTypeFolders)

# Checkbox: Series Folders
$chkSeriesFolders = New-Object System.Windows.Forms.CheckBox
$chkSeriesFolders.Location = New-Object System.Drawing.Point(105, 220)
$chkSeriesFolders.Size = New-Object System.Drawing.Size(400, 20)
$chkSeriesFolders.Text = "Auto-Create Series Folders (e.g., Mario, Pokemon)"
$chkSeriesFolders.Checked = $true
$form.Controls.Add($chkSeriesFolders)

# Checkbox: Auto-Split Alphabetical
$chkAZFolders = New-Object System.Windows.Forms.CheckBox
$chkAZFolders.Location = New-Object System.Drawing.Point(105, 245)
$chkAZFolders.Size = New-Object System.Drawing.Size(400, 20)
$chkAZFolders.Text = "Subdivide loose games into A-Z Folders (A, B, C...)"
$chkAZFolders.Checked = $true
$form.Controls.Add($chkAZFolders)

# Checkbox: 1G1R Filter
$chk1G1R = New-Object System.Windows.Forms.CheckBox
$chk1G1R.Location = New-Object System.Drawing.Point(85, 270)
$chk1G1R.Size = New-Object System.Drawing.Size(400, 20)
$chk1G1R.Text = "1G1R Filter: Keep only the best region per game"
$chk1G1R.Checked = $false
$chk1G1R.Add_CheckedChanged({
        $chkRegionUSA.Enabled = $chk1G1R.Checked
        $chkRegionWorld.Enabled = $chk1G1R.Checked
        $chkRegionEur.Enabled = $chk1G1R.Checked
        $chkRegionJpn.Enabled = $chk1G1R.Checked
    })
$form.Controls.Add($chk1G1R)

# Region: USA
$chkRegionUSA = New-Object System.Windows.Forms.CheckBox
$chkRegionUSA.Location = New-Object System.Drawing.Point(105, 290)
$chkRegionUSA.Size = New-Object System.Drawing.Size(80, 20)
$chkRegionUSA.Text = "USA (1)"
$chkRegionUSA.Checked = $true
$chkRegionUSA.Enabled = $false
$form.Controls.Add($chkRegionUSA)

# Region: World
$chkRegionWorld = New-Object System.Windows.Forms.CheckBox
$chkRegionWorld.Location = New-Object System.Drawing.Point(185, 290)
$chkRegionWorld.Size = New-Object System.Drawing.Size(80, 20)
$chkRegionWorld.Text = "World (2)"
$chkRegionWorld.Checked = $true
$chkRegionWorld.Enabled = $false
$form.Controls.Add($chkRegionWorld)

# Region: Europe
$chkRegionEur = New-Object System.Windows.Forms.CheckBox
$chkRegionEur.Location = New-Object System.Drawing.Point(265, 290)
$chkRegionEur.Size = New-Object System.Drawing.Size(80, 20)
$chkRegionEur.Text = "Europe (3)"
$chkRegionEur.Checked = $true
$chkRegionEur.Enabled = $false
$form.Controls.Add($chkRegionEur)

# Region: Japan
$chkRegionJpn = New-Object System.Windows.Forms.CheckBox
$chkRegionJpn.Location = New-Object System.Drawing.Point(345, 290)
$chkRegionJpn.Size = New-Object System.Drawing.Size(80, 20)
$chkRegionJpn.Text = "Japan (4)"
$chkRegionJpn.Checked = $true
$chkRegionJpn.Enabled = $false
$form.Controls.Add($chkRegionJpn)

# Checkbox: Zip Support
$chkZip = New-Object System.Windows.Forms.CheckBox
$chkZip.Location = New-Object System.Drawing.Point(85, 320)
$chkZip.Size = New-Object System.Drawing.Size(400, 20)
$chkZip.Text = "Extract ROMs from .zip files"
$chkZip.Checked = $false
$form.Controls.Add($chkZip)

# Checkbox: Keep Tags
$chkKeepTags = New-Object System.Windows.Forms.CheckBox
$chkKeepTags.Location = New-Object System.Drawing.Point(85, 345)
$chkKeepTags.Size = New-Object System.Drawing.Size(400, 20)
$chkKeepTags.Text = "Keep Original Tags (Prevents overwriting multiple versions)"
$chkKeepTags.Checked = $true
$form.Controls.Add($chkKeepTags)

# Checkbox: Backup Saves
$chkBackupSaves = New-Object System.Windows.Forms.CheckBox
$chkBackupSaves.Location = New-Object System.Drawing.Point(85, 370)
$chkBackupSaves.Size = New-Object System.Drawing.Size(400, 20)
$chkBackupSaves.Text = "Backup SD .sav/.srm/.rtc files to PC before cleaning"
$chkBackupSaves.Checked = $true
$form.Controls.Add($chkBackupSaves)

# Log Box
$txtLog = New-Object System.Windows.Forms.TextBox
$txtLog.Location = New-Object System.Drawing.Point(15, 395)
$txtLog.Size = New-Object System.Drawing.Size(500, 255)
$txtLog.Multiline = $true
$txtLog.ScrollBars = "Vertical"
$txtLog.ReadOnly = $true
$txtLog.BackColor = [System.Drawing.Color]::White
$txtLog.Font = New-Object System.Drawing.Font("Consolas", 8)
$form.Controls.Add($txtLog)

# Progress Bar
$progressBar = New-Object System.Windows.Forms.ProgressBar
$progressBar.Location = New-Object System.Drawing.Point(15, 660)
$progressBar.Size = New-Object System.Drawing.Size(500, 20)
$progressBar.Style = [System.Windows.Forms.ProgressBarStyle]::Continuous
$form.Controls.Add($progressBar)

# Log Box Helper Function
function Write-UiMsg($msg) {
    if ($txtLog.Text.Length -gt 0) {
        $txtLog.AppendText("`r`n")
    }
    $txtLog.AppendText($msg)
    $txtLog.SelectionStart = $txtLog.Text.Length
    $txtLog.ScrollToCaret()
    [System.Windows.Forms.Application]::DoEvents()
}

function Update-UiProgress {
    if ($progressBar.Value -lt $progressBar.Maximum) {
        $progressBar.Value += 1
    }
}

# --- Standard Mirror Copy ---
function Copy-ItemsSorted {
    param ([string]$SrcPath, [string]$DestPath)

    if (-not (Test-Path -LiteralPath $DestPath)) {
        New-Item -ItemType Directory -Path $DestPath -Force | Out-Null
        Write-UiMsg "Created Folder: $(Split-Path $DestPath -Leaf)"
    }

    $items = Get-ChildItem -LiteralPath $SrcPath | Sort-Object -Property @{Expression = { $_.PSIsContainer }; Descending = $true }, @{Expression = { $_.Name }; Ascending = $true }

    foreach ($item in $items) {
        $destItemPath = Join-Path -Path $DestPath -ChildPath $item.Name
        if ($item.PSIsContainer) {
            Copy-ItemsSorted -SrcPath $item.FullName -DestPath $destItemPath
        }
        else {
            if (Test-Path -LiteralPath $destItemPath) {
                $destFile = Get-Item -LiteralPath $destItemPath
                if ($destFile.Length -eq $item.Length -and $destFile.LastWriteTime -eq $item.LastWriteTime) {
                    Update-UiProgress
                    continue
                }
                Remove-Item -LiteralPath $destItemPath -Force
            }
            Write-UiMsg " -> Copying: $($item.Name)"
            Copy-Item -LiteralPath $item.FullName -Destination $destItemPath -Force
            Update-UiProgress
        }
    }
}

# --- Virtual Tree for Reorganization ---
function Add-ToVirtualTree {
    param($RootNode, [string]$SourcePath, [string[]]$DestParts, [switch]$FolderOnly)
    
    $currentNode = $RootNode
    # Filter out empty segments to prevent "empty parts" bug which causes folders to be created instead of files
    $cleanParts = @($DestParts | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    
    for ($i = 0; $i -lt $cleanParts.Length; $i++) {
        $part = $cleanParts[$i]
        
        $isLast = ($i -eq ($cleanParts.Length - 1))
        $isFolder = if ($FolderOnly) { $true } else { -not $isLast }
        
        $child = $null
        foreach ($c in $currentNode.Children) {
            if ($c.Name -eq $part) {
                # If we previously thought this was a file but now need it to be a folder, upgrade it
                if ($isFolder -and -not $c.IsFolder) {
                    $c.IsFolder = $true
                }
                $child = $c
                break
            }
        }
        
        if ($null -eq $child) {
            $child = @{
                Name       = $part
                IsFolder   = $isFolder
                SourcePath = $(if ($isFolder) { $null } else { $SourcePath })
                Children   = New-Object System.Collections.ArrayList
            }
            [void]$currentNode.Children.Add($child)
        }
        
        $currentNode = $child
    }
}

function Copy-VirtualTree {
    param($Node, $CurrentDestPath, $SdCatalog)
    
    if (-not $Node.Children -or $Node.Children.Count -eq 0) { return }

    $sortedChildren = $Node.Children | Sort-Object -Property @{Expression = { $_.IsFolder }; Descending = $true }, @{Expression = { $_.Name }; Ascending = $true }
    
    foreach ($child in $sortedChildren) {
        $targetName = $child.Name
        $projectedLength = $CurrentDestPath.Length + 1 + $targetName.Length
        if ($projectedLength -gt 240) {
            $allowedChars = 240 - ($CurrentDestPath.Length + 1)
            if (-not $child.IsFolder -and $targetName -match '\.[^\.]+$') {
                $ext = $matches[0]
                $base = $targetName.Substring(0, $targetName.Length - $ext.Length)
                if ($allowedChars -gt $ext.Length) {
                    $targetName = $base.Substring(0, $allowedChars - $ext.Length) + $ext
                }
            }
            else {
                if ($allowedChars -gt 0) {
                    $targetName = $targetName.Substring(0, $allowedChars)
                }
            }
        }
    
        $targetPath = Join-Path $CurrentDestPath $targetName
        
        if ($child.IsFolder) {
            if (-not (Test-Path -LiteralPath $targetPath)) {
                New-Item -ItemType Directory -Path $targetPath -Force | Out-Null
                Write-UiMsg "Created Folder: $(Split-Path $targetPath -Leaf)"
            }
            Copy-VirtualTree -Node $child -CurrentDestPath $targetPath -SdCatalog $SdCatalog
        }
        else {
            if ([string]::IsNullOrWhiteSpace($child.SourcePath)) {
                Write-UiMsg " !! Skipping $($child.Name) (No source path)"
                Update-UiProgress
                continue
            }
            $sourceFile = Get-Item -LiteralPath $child.SourcePath
            # Signature must match the one generated during SD cataloging (uses source/sd filename, not cleaned folder name)
            $fileSignature = "$($sourceFile.Length)_$($sourceFile.LastWriteTime.Ticks)_$($sourceFile.Name)"
            $mappedSdFile = $null

            if ($SdCatalog.ContainsKey($fileSignature)) {
                $mappedSdFile = ($SdCatalog[$fileSignature] | Select-Object -First 1)
            }
            
            if (Test-Path -LiteralPath $targetPath) {
                # File is already exactly where it needs to be with the correct data
                $destFile = Get-Item -LiteralPath $targetPath
                if ($destFile.Length -eq $sourceFile.Length -and $destFile.LastWriteTime -eq $sourceFile.LastWriteTime) {
                    if ($mappedSdFile -and $mappedSdFile.FullName -eq $targetPath) {
                        $SdCatalog[$fileSignature].Remove($mappedSdFile) | Out-Null
                    }
                    Update-UiProgress
                    continue
                }
                Write-UiMsg " !! Correcting Type Conflict: $($child.Name) (Cleaning directory for file replacement)"
                Remove-Item -LiteralPath $targetPath -Force -Recurse
            }
            
            if ($mappedSdFile) {
                # File exists somewhere else on the SD card, let's just move it instantly
                Write-UiMsg " -> Moving (Local): $($child.Name) to $(Split-Path $CurrentDestPath -Leaf)"
                Move-Item -LiteralPath $mappedSdFile.FullName -Destination $targetPath -Force
                $SdCatalog[$fileSignature].Remove($mappedSdFile) | Out-Null
                if ($SdCatalog[$fileSignature].Count -eq 0) {
                    $SdCatalog.Remove($fileSignature)
                }
                Update-UiProgress
                continue
            }
            
            # File is completely new, we must copy it over
            Write-UiMsg " -> Copying (USB): $($child.Name)"
            Copy-Item -LiteralPath $child.SourcePath -Destination $targetPath -Force
            Update-UiProgress
        }
    }
}

# --- ROM Name Sanitizer ---
function Get-CleanRomName {
    param([string]$BaseName, [switch]$PreserveTags)
    
    $clean = $BaseName
    
    $suffix = ""
    if ($clean -match '(?i)(Hack|Translation|Patched)') {
        $suffix = " [Hack]"
    }
    
    if (-not $PreserveTags) {
        # 1. Strip No-Intro Region/Revision tags like (USA, Europe), (Rev A), [!], (SGB Enhanced)
        # Including \s* to consume leading/trailing spaces around the tags so they don't leave double spaces behind
        $clean = $clean -replace '\s*\([^)]+\)\s*', ' '
        $clean = $clean -replace '\s*\[[^\]]+\]\s*', ' '
    }
    
    # 2. Fix the "Pokémon" accents so it matches "Pokemon" folders perfectly and sorts correctly
    # We use .NET Unicode normalization to strip accents so it works regardless of text encoding
    if ($clean -match '[^\x00-\x7F]') {
        $clean = [string]::Join('', ($clean.Normalize([System.Text.NormalizationForm]::FormD).ToCharArray() | Where-Object { 
                    [System.Globalization.CharUnicodeInfo]::GetUnicodeCategory($_) -ne [System.Globalization.UnicodeCategory]::NonSpacingMark 
                }))
    }
    
    # 3. Clean up loose underscores, replacing them all with spaces
    # We leave hyphens alone so games like "Legend of Zelda, The - Oracle of Ages" keep their expected punctuation
    $clean = $clean -replace '_+', ' '
    
    # 4. Clean up trailing/leading whitespace and double spaces left behind
    $clean = $clean -replace '\s+', ' '
    $clean = $clean.Trim()
    
    # 5. Fix "The " prefix for alphabetical sorting ("The Legend of Zelda" -> "Legend of Zelda, The")
    if ($clean -match '^(?i)The\s+(.+)$') {
        $clean = $matches[1] + ", The"
    }

    $final = ($clean + $suffix).Trim()
    if ([string]::IsNullOrWhiteSpace($final)) { return $BaseName }
    return $final
}

# --- 1G1R Filter Logic ---
function Get-BestRegionGames {
    param([System.IO.FileInfo[]]$Files, [switch]$USA, [switch]$World, [switch]$Eur, [switch]$Jpn)
    
    $bestGames = New-Object System.Collections.Generic.List[System.IO.FileInfo]
    $groupedByCleanName = @{}
    
    foreach ($f in $Files) {
        $clean = Get-CleanRomName -BaseName $f.BaseName
        if (-not $groupedByCleanName.ContainsKey($clean)) {
            $groupedByCleanName[$clean] = New-Object System.Collections.Generic.List[System.IO.FileInfo]
        }
        $groupedByCleanName[$clean].Add($f)
    }
    
    foreach ($group in $groupedByCleanName.Values) {
        if ($group.Count -eq 1) {
            $bestGames.Add($group[0])
            continue
        }
        
        # We have duplicates. Rank them by region/version. Lower score = better.
        $bestGame = $null
        $bestScore = 999
        
        foreach ($f in $group) {
            $name = $f.BaseName
            $score = 500
            
            if ($name -match '\(USA') { 
                if ($USA) { $score = 10 } else { continue }
            }
            elseif ($name -match '\(World') { 
                if ($World) { $score = 20 } else { continue }
            }
            elseif ($name -match '\(Europe') { 
                if ($Eur) { $score = 30 } else { continue }
            }
            elseif ($name -match '\(Japan') { 
                if ($Jpn) { $score = 80 } else { continue }
            }
            else {
                # If it doesn't have a region tag, it's probably standard/USA or we should keep it
                $score = 50 
            }
            
            # Prefer newer revisions if multiple USA/EU exist
            if ($name -match '\(Rev ([0-9]+|[A-Z]+)\)') { 
                $rev = $matches[1]
                if ($rev -eq '1' -or $rev -eq 'A') { $score -= 1 }
                else { $score -= 2 }
            }
            
            # Keep Bugfixes and Hacks over the original broken base ROM
            if ($name -match '(?i)Bugfix') { $score -= 5 }
            elseif ($name -match '(?i)Hack') { $score -= 4 }
            
            if ($score -lt $bestScore) {
                $bestScore = $score
                $bestGame = $f
            }
        }
        
        if ($bestGame) {
            $bestGames.Add($bestGame)
        }
    }
    
    return $bestGames.ToArray()
}

# --- Series Matching Logic ---
function Get-SeriesGroups {
    param([System.IO.FileInfo[]]$Files)
    
    $mapping = @{}
    if ($Files.Count -lt 2) {
        foreach ($f in $Files) { $mapping[$f.FullName] = "" }
        return $mapping
    }

    $knownFranchises = @(
        "Pokemon", "Mario", "Zelda", "Donkey Kong", "Wario", "Mega Man", 
        "Castlevania", "Bomberman", "Final Fantasy", "Dragon Quest", 
        "Kirby", "Tetris", "Metroid", "Street Fighter", "Mortal Kombat",
        "Tomb Raider", "Resident Evil", "Tony Hawk", "Pac-Man", "Crash Bandicoot",
        "Rayman", "Harvest Moon", "Star Wars", "Disney", "Batman", "Spider-Man",
        "Yu-Gi-Oh", "Harry Potter", "Ninja Turtles"
    )

    $assignedFiles = New-Object System.Collections.Generic.HashSet[string]
    
    # 1. First Pass: Known Franchises
    foreach ($f in $Files) {
        $cleanName = Get-CleanRomName -BaseName $f.BaseName
        foreach ($franchise in $knownFranchises) {
            # Ensure word boundaries so "Mario" doesn't catch "Marionette"
            if ($cleanName -match "(?i)\b$([regex]::Escape($franchise))\b") {
                $mapping[$f.FullName] = $franchise
                [void]$assignedFiles.Add($f.FullName)
                break
            }
        }
    }

    # 2. Second Pass: LCP for remaining files
    $prefixFiles = @{} 
    $unassignedFiles = @($Files | Where-Object { -not $assignedFiles.Contains($_.FullName) })

    for ($i = 0; $i -lt $unassignedFiles.Count; $i++) {
        [System.Windows.Forms.Application]::DoEvents()
        for ($j = $i + 1; $j -lt $unassignedFiles.Count; $j++) {
            $name1 = Get-CleanRomName -BaseName $unassignedFiles[$i].BaseName
            $name2 = Get-CleanRomName -BaseName $unassignedFiles[$j].BaseName
            
            # Remove subtitles after " - " or ": " before prefix matching
            $name1 = $name1 -replace '\s*[:-].*', ''
            $name2 = $name2 -replace '\s*[:-].*', ''

            $words1 = @($name1 -split '[\s_]+' | Where-Object { $_.Trim().Length -gt 0 })
            $words2 = @($name2 -split '[\s_]+' | Where-Object { $_.Trim().Length -gt 0 })
            
            $lcpWords = @()
            for ($k = 0; $k -lt [Math]::Min($words1.Length, $words2.Length); $k++) {
                if ($words1[$k] -eq $words2[$k]) {
                    $lcpWords += $words1[$k]
                }
                else {
                    break
                }
            }
            
            if ($lcpWords.Length -ge 1) {
                $prefix = $lcpWords -join ' '
                
                # STRICTER RULES:
                # 1. Require at least two words for auto-prefixes
                if ($lcpWords.Length -lt 2) {
                    continue
                }
                
                if (-not $prefixFiles.ContainsKey($prefix)) {
                    $prefixFiles[$prefix] = New-Object System.Collections.Generic.HashSet[string]
                }
                [void]$prefixFiles[$prefix].Add($unassignedFiles[$i].FullName)
                [void]$prefixFiles[$prefix].Add($unassignedFiles[$j].FullName)
            }
        }
    }
    
    $validPrefixes = @()
    foreach ($prefix in $prefixFiles.Keys) {
        $validPrefixes += [PSCustomObject]@{
            Prefix    = $prefix
            WordCount = ($prefix -split ' ').Length
            FileCount = $prefixFiles[$prefix].Count
            Files     = $prefixFiles[$prefix]
        }
    }
    
    # Sort: Smallest word count first to find the BROADEST base prefix
    $sortedPrefixes = $validPrefixes | Sort-Object -Property @{Expression = { $_.WordCount }; Ascending = $true }, @{Expression = { $_.FileCount }; Descending = $true }
    
    foreach ($p in $sortedPrefixes) {
        $unassignedForThisPrefix = @()
        foreach ($f in $p.Files) {
            if (-not $assignedFiles.Contains($f)) {
                $unassignedForThisPrefix += $f
            }
        }
        
        # STRICTER RULES:
        # Require at least 3 games for an auto-generated series
        if ($unassignedForThisPrefix.Count -ge 3) {
            foreach ($f in $unassignedForThisPrefix) {
                $mapping[$f] = $p.Prefix
                [void]$assignedFiles.Add($f)
            }
        }
    }
    
    # 3. Final Pass: Map anything remaining to root
    foreach ($f in $Files) {
        if (-not $assignedFiles.Contains($f.FullName)) {
            $mapping[$f.FullName] = ""
        }
    }
    
    return $mapping
}

$btnStart = New-Object System.Windows.Forms.Button
$btnStart.Location = New-Object System.Drawing.Point(210, 690)
$btnStart.Size = New-Object System.Drawing.Size(120, 30)
$btnStart.Text = "Start Sync"
$btnStart.BackColor = [System.Drawing.Color]::LightGreen

$btnStart.Add_Click({
        $source = $txtSource.Text
        $hacksSource = $txtHacks.Text
        $gbcSysPayload = $txtGbcSysPayload.Text
        $dest = $txtDest.Text

        $sourceValid = (-not [string]::IsNullOrWhiteSpace($source) -and (Test-Path -LiteralPath $source))
        $hacksValid = (-not [string]::IsNullOrWhiteSpace($hacksSource) -and (Test-Path -LiteralPath $hacksSource))

        if (-not $sourceValid -and -not $hacksValid) {
            [System.Windows.Forms.MessageBox]::Show("At least one Source path must exist.", "Error", 0, [System.Windows.Forms.MessageBoxIcon]::Error)
            return
        }
        if ([string]::IsNullOrWhiteSpace($dest)) {
            [System.Windows.Forms.MessageBox]::Show("Please select an SD Card destination.", "Error", 0, [System.Windows.Forms.MessageBoxIcon]::Error)
            return
        }

        if (-not (Test-Path -LiteralPath $dest)) {
            [System.Windows.Forms.MessageBox]::Show("Destination path does not exist. Please check your SD card path.", "Error", 0, [System.Windows.Forms.MessageBoxIcon]::Error)
            return
        }

        # --- Self-Sync Prevention ---
        $srcFull = if ($sourceValid) { (Get-Item -LiteralPath $source).FullName } else { "" }
        $hacksFull = if ($hacksValid) { (Get-Item -LiteralPath $hacksSource).FullName } else { "" }
        $destFull = (Get-Item -LiteralPath $dest).FullName

        if (($srcFull -eq $destFull) -or ($hacksFull -eq $destFull)) {
            [System.Windows.Forms.MessageBox]::Show("Source and Destination cannot be the same. This would cause a 'Self-Sync' loop and duplicate your library into backups.", "Error", 0, [System.Windows.Forms.MessageBoxIcon]::Error)
            return
        }

        # --- Destination Safety Checks ---
        $sysDrive = [System.IO.Path]::GetPathRoot($env:SystemRoot)
        $destRoot = [System.IO.Path]::GetPathRoot($destFull)
        
        if ($destRoot -eq $sysDrive) {
            $warnMsg = "WARNING: You selected a folder on your System Drive ($sysDrive) as the SD Card destination.`n`nThis script performs DESTRUCTIVE operations (deleting and overwriting files). It is highly recommended to ONLY target an external SD card.`n`nAre you ABSOLUTELY sure you want to proceed and potentially delete files in:`n$destFull ?"
            $res = [System.Windows.Forms.MessageBox]::Show($warnMsg, "DANGER: System Drive Selected", 1, [System.Windows.Forms.MessageBoxIcon]::Warning)
            if ($res -ne [System.Windows.Forms.DialogResult]::OK) { return }
        }

        # Check for EverDrive OS folders to prevent wiping regular external/backup drives
        $hasEverDriveOS = (Test-Path -LiteralPath (Join-Path $dest "EDGB")) -or 
        (Test-Path -LiteralPath (Join-Path $dest "GBOS")) -or 
        (Test-Path -LiteralPath (Join-Path $dest "GBCSYS"))
        
        if (-not $hasEverDriveOS) {
            [System.Windows.Forms.MessageBox]::Show("CRITICAL ERROR: The selected destination ($destFull) does not appear to be an EverDrive SD card because it is missing the standard system folder (EDGB, GBOS, or GBCSYS).`n`nTo protect against accidental data loss on external and backup drives, the sync has been blocked.`n`nIf this is a new SD card, please copy your EverDrive OS files to the SD card first before syncing.", "Invalid Destination", 0, [System.Windows.Forms.MessageBoxIcon]::Error)
            return
        }
        elseif ($destRoot -ne $sysDrive) {
            $warnMsg2 = "WARNING: This will permanently DELETE all non-system files on drive [$destRoot] (in $destFull).`n`nAre you absolutely sure you want to proceed?"
            $res2 = [System.Windows.Forms.MessageBox]::Show($warnMsg2, "Confirm Deletion", 1, [System.Windows.Forms.MessageBoxIcon]::Warning)
            if ($res2 -ne [System.Windows.Forms.DialogResult]::OK) { return }
        }



        # Determine standard OS folder for EverDrive saves (EDGB, GBOS, or GBCSYS)
        $osFolder = [string]"EDGB"
        if (Test-Path -LiteralPath (Join-Path $dest "GBOS")) { $osFolder = "GBOS" }
        elseif (Test-Path -LiteralPath (Join-Path $dest "GBCSYS")) { $osFolder = "GBCSYS" }
        elseif (Test-Path -LiteralPath (Join-Path $dest "EDGB")) { $osFolder = "EDGB" }

        if ($osFolder -eq "GBOS") { 
            $saveSubDirBase = "SAVES"
            $rtcSubDirBase = "SAVES"
        }
        else { 
            $saveSubDirBase = "SAVE"
            $rtcSubDirBase = "RTC"
        }

        # Save Config
        $configObj = @{ Source = $source; Hacks = $hacksSource; GbcSysPayload = $gbcSysPayload; Dest = $dest }
        $configObj | ConvertTo-Json | Set-Content -LiteralPath $configPath -Force

        $btnStart.Enabled = $false
        $txtSource.Enabled = $false
        $txtHacks.Enabled = $false
        $txtGbcSysPayload.Enabled = $false
        $txtDest.Enabled = $false
        $btnSource.Enabled = $false
        $btnHacks.Enabled = $false
        $btnGbcSysPayload.Enabled = $false
        $btnDest.Enabled = $false
        $chkGroup.Enabled = $false
        $chkTypeFolders.Enabled = $false
        $chkSeriesFolders.Enabled = $false
        $chk1G1R.Enabled = $false
        $chkZip.Enabled = $false
        $chkKeepTags.Enabled = $false
        $chkAZFolders.Enabled = $false
        $chkBackupSaves.Enabled = $false
        $chkRegionUSA.Enabled = $false
        $chkRegionWorld.Enabled = $false
        $chkRegionEur.Enabled = $false
        $chkRegionJpn.Enabled = $false

        $txtLog.Clear()
        $progressBar.Value = 0

        Write-UiMsg "Starting Alphabetical Sync..."
        Write-UiMsg "Source: $source"
        Write-UiMsg "Dest:   $dest"
        Write-UiMsg "----------------------------------------"

        $tempUnzipDir = ""
        try {
            if ($chkBackupSaves.Checked -and (Test-Path -LiteralPath $dest)) {
                Write-UiMsg "Backing up .sav, .srm, .fla, and .rtc files to PC..."
                $backupDir = Join-Path $source "Saves_Backup"
                if (-not (Test-Path -LiteralPath $backupDir)) {
                    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
                }
                $savesOnSD = Get-ChildItem -LiteralPath $dest -File -Recurse | Where-Object { $_.Extension -match '(?i)^\.(sav|rtc|srm|fla)$' }
                $saveCount = 0
                foreach ($s in $savesOnSD) {
                    # Generate a relative path within the EverDrive OS folder (EDGB, GBCSYS, etc.)
                    $relPath = if ($s.FullName -match "(?i)[\\/]$osFolder[\\/](.+)$") { $matches[1] } else { $s.Name }
                    $saveDest = Join-Path $backupDir $relPath
                    $saveDestDir = Split-Path $saveDest
                    if (-not (Test-Path -LiteralPath $saveDestDir)) { New-Item -ItemType Directory -Path $saveDestDir -Force | Out-Null }
                    Copy-Item -LiteralPath $s.FullName -Destination $saveDest -Force
                    $saveCount++
                }
                Write-UiMsg "Backed up $saveCount .sav/.srm/.rtc files."
            }

            Write-UiMsg "Formatting destination directory (Preserving EverDrive OS folders)..."
            if (Test-Path -LiteralPath $dest) {
                $itemsToClean = Get-ChildItem -LiteralPath $dest | Where-Object { 
                    $_.Name -notmatch '(?i)^(EDGB|GBOS|GBCSYS|System Volume Information)$' 
                }
                foreach ($i in $itemsToClean) {
                    Remove-Item -LiteralPath $i.FullName -Recurse -Force -ErrorAction SilentlyContinue
                }
                Write-UiMsg "Destination formatted."
            }

            $sdCatalog = @{}

            Write-UiMsg "Analyzing files..."
            
            # Unzip Logic
            if ($chkZip.Checked -and $sourceValid) {
                $zipFiles = Get-ChildItem -LiteralPath $source -Filter "*.zip" -Recurse
                if ($zipFiles.Count -gt 0) {
                    Add-Type -AssemblyName System.IO.Compression.FileSystem
                    $tempUnzipDir = Join-Path ([System.IO.Path]::GetTempPath()) "EverDrive_Unzip_$([guid]::NewGuid().ToString().Substring(0,8))"
                    New-Item -ItemType Directory -Path $tempUnzipDir | Out-Null
                    
                    Write-UiMsg "Extracting $($zipFiles.Count) zip files to temp directory..."
                    $progressBar.Maximum = $zipFiles.Count
                    
                    foreach ($zip in $zipFiles) {
                        try {
                            $zipStream = [System.IO.Compression.ZipFile]::OpenRead($zip.FullName)
                            foreach ($entry in $zipStream.Entries) {
                                if ($entry.Name -match '\.(gb|gbc)$') {
                                    $entryDest = Join-Path $tempUnzipDir $entry.Name
                                    [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $entryDest, $true)
                                }
                            }
                            $zipStream.Dispose()
                        }
                        catch { Write-UiMsg "Failed to extract $($zip.Name)" }
                        Update-UiProgress
                    }
                    $progressBar.Value = 0
                }
            }
            
            # Collect all loose files
            $allFiles = @()
            if ($sourceValid) {
                Write-UiMsg "Scanning source folders..."
                $allFiles = @(Get-ChildItem -LiteralPath $source -File -Recurse | Where-Object { 
                        $_.Name -notmatch '(?i)^(\._|\.DS_Store)' -and 
                        $_.Extension -notmatch '(?i)^\.zip$' -and
                        $_.DirectoryName -notmatch '(?i)[\\/](Saves_Backup|GBCSYS|GBOS|EDGB)([\\/]?|$)'
                    })
            }
            
            if ($tempUnzipDir -and (Test-Path -Path $tempUnzipDir)) {
                $allFiles += @(Get-ChildItem -LiteralPath $tempUnzipDir -File -Recurse)
            }

            if ($allFiles.Count -eq 0 -and -not $hacksSource) {
                throw "No files found to sync! Please check your source path."
            }

            if ($chkGroup.Checked) {
                if ($chkSeriesFolders.Checked) {
                    Write-UiMsg "Analyzing files for Series grouping... (This can take 20-40 seconds for massive libraries)"
                }
            
                $gbFiles = @($allFiles | Where-Object { $_.Extension -match '(?i)^\.gb$' })
                $gbcFiles = @($allFiles | Where-Object { $_.Extension -match '(?i)^\.gbc$' })
                $savFiles = @($allFiles | Where-Object { $_.Extension -match '(?i)^\.(sav|rtc|srm|fla)$' })
                $otherFiles = @($allFiles | Where-Object { $_.Extension -notmatch '(?i)^\.(gb|gbc|sav|rtc|srm|fla|zip)$' })

                if ($chk1G1R.Checked) {
                    Write-UiMsg "Applying 1G1R filter (Ranking: USA > World > Europe > Japan)..."
                    $gbFiles = Get-BestRegionGames -Files $gbFiles -USA:$chkRegionUSA.Checked -World:$chkRegionWorld.Checked -Eur:$chkRegionEur.Checked -Jpn:$chkRegionJpn.Checked
                    $gbcFiles = Get-BestRegionGames -Files $gbcFiles -USA:$chkRegionUSA.Checked -World:$chkRegionWorld.Checked -Eur:$chkRegionEur.Checked -Jpn:$chkRegionJpn.Checked
                }

                if ($chkSeriesFolders.Checked) {
                    $gbGroups = Get-SeriesGroups -Files $gbFiles
                    $gbcGroups = Get-SeriesGroups -Files $gbcFiles
                }
                else {
                    $gbGroups = @{}
                    $gbcGroups = @{}
                }
                $vRoot = @{ Name = ""; IsFolder = $true; Children = New-Object System.Collections.ArrayList }
                $romNameMap = @{}

                function Get-FuzzyTitle {
                    param([string]$BaseName)
                    $t = $BaseName -replace '\s*\([^)]+\)\s*', ' '
                    $t = $t -replace '\s*\[[^\]]+\]\s*', ' '
                    $t = $t -replace '[-_]', ' '
                    $t = $t -replace '\s+', ' '
                    return $t.Trim().ToLower()
                }

                # Process GB
                foreach ($f in $gbFiles) {
                    $group = if ($chkSeriesFolders.Checked) { $gbGroups[$f.FullName] } else { "" }
                    $destParts = @()
                    if ($chkTypeFolders.Checked) { $destParts += "GB" }
                    if (-not [string]::IsNullOrWhiteSpace($group)) { $destParts += $group }
                    else {
                        if ($chkAZFolders.Checked) {
                            $cleanNameForAZ = Get-CleanRomName -BaseName $f.BaseName
                            $firstChar = if ($cleanNameForAZ.Length -gt 0) { $cleanNameForAZ.Substring(0, 1).ToUpper() } else { "#" }
                            if ($firstChar -match '[A-Z]') { $destParts += $firstChar } else { $destParts += "#" }
                        }
                    }
                    $finalRomName = (Get-CleanRomName -BaseName $f.BaseName -PreserveTags:$chkKeepTags.Checked)
                    $destParts += ($finalRomName + $f.Extension)
                    Add-ToVirtualTree -RootNode $vRoot -SourcePath $f.FullName -DestParts $destParts
                    $fuzzy = Get-FuzzyTitle -BaseName $f.BaseName
                    if (-not $romNameMap.ContainsKey($fuzzy)) { $romNameMap[$fuzzy] = $finalRomName }
                }

                # Process GBC
                foreach ($f in $gbcFiles) {
                    $group = if ($chkSeriesFolders.Checked) { $gbcGroups[$f.FullName] } else { "" }
                    $destParts = @()
                    if ($chkTypeFolders.Checked) { $destParts += "GBC" }
                    if (-not [string]::IsNullOrWhiteSpace($group)) { $destParts += $group }
                    else {
                        if ($chkAZFolders.Checked) {
                            $cleanNameForAZ = Get-CleanRomName -BaseName $f.BaseName
                            $firstChar = if ($cleanNameForAZ.Length -gt 0) { $cleanNameForAZ.Substring(0, 1).ToUpper() } else { "#" }
                            if ($firstChar -match '[A-Z]') { $destParts += $firstChar } else { $destParts += "#" }
                        }
                    }
                    $finalRomName = (Get-CleanRomName -BaseName $f.BaseName -PreserveTags:$chkKeepTags.Checked)
                    $destParts += ($finalRomName + $f.Extension)
                    Add-ToVirtualTree -RootNode $vRoot -SourcePath $f.FullName -DestParts $destParts
                    $fuzzy = Get-FuzzyTitle -BaseName $f.BaseName
                    if (-not $romNameMap.ContainsKey($fuzzy)) { $romNameMap[$fuzzy] = $finalRomName }
                }

                # Process ROM Hacks (Aligned with main library rules)
                if (-not [string]::IsNullOrWhiteSpace($hacksSource) -and (Test-Path -LiteralPath $hacksSource)) {
                    Write-UiMsg "Analyzing ROM Hacks..."
                    $hackFilesRaw = @(Get-ChildItem -LiteralPath $hacksSource -File -Recurse | Where-Object { $_.Name -notmatch '(?i)^(\._|\.DS_Store)' -and $_.Extension -match '(?i)^\.gbc?$' })
                    
                    if ($chk1G1R.Checked) {
                        $hackFilesRaw = Get-BestRegionGames -Files $hackFilesRaw -USA:$chkRegionUSA.Checked -World:$chkRegionWorld.Checked -Eur:$chkRegionEur.Checked -Jpn:$chkRegionJpn.Checked
                    }

                    if ($chkSeriesFolders.Checked) {
                        $hackGroups = Get-SeriesGroups -Files $hackFilesRaw
                    }
                    else {
                        $hackGroups = @{}
                    }
                    
                    foreach ($f in $hackFilesRaw) {
                        $destParts = @("[ROM Hacks]")
                        $group = if ($chkSeriesFolders.Checked) { $hackGroups[$f.FullName] } else { "" }
                        
                        if (-not [string]::IsNullOrWhiteSpace($group)) { $destParts += $group }
                        else {
                            if ($chkAZFolders.Checked) {
                                $cleanNameForAZ = Get-CleanRomName -BaseName $f.BaseName
                                $firstChar = if ($cleanNameForAZ.Length -gt 0) { $cleanNameForAZ.Substring(0, 1).ToUpper() } else { "#" }
                                if ($firstChar -match '[A-Z]') { $destParts += $firstChar } else { $destParts += "#" }
                            }
                        }
                        
                        $finalRomName = (Get-CleanRomName -BaseName $f.BaseName -PreserveTags:$chkKeepTags.Checked)
                        $destParts += ($finalRomName + $f.Extension)
                        Add-ToVirtualTree -RootNode $vRoot -SourcePath $f.FullName -DestParts $destParts
                        
                        $fuzzy = Get-FuzzyTitle -BaseName $f.BaseName
                        if (-not $romNameMap.ContainsKey($fuzzy)) { $romNameMap[$fuzzy] = $finalRomName }
                    }

                    # Collect non-ROM hack files (readme, images, etc.)
                    $otherHackFiles = @(Get-ChildItem -LiteralPath $hacksSource -File -Recurse | Where-Object { $_.Extension -notmatch '(?i)^\.(gbc?|sav|srm|rtc|fla|zip)$' })
                    foreach ($f in $otherHackFiles) {
                        if ($f.FullName.StartsWith($hacksSource, [System.StringComparison]::InvariantCultureIgnoreCase)) {
                            $rel = $f.FullName.Substring($hacksSource.Length).TrimStart('\', '/')
                            $parts = @("[ROM Hacks]") + ($rel -split '[\\/]')
                            Add-ToVirtualTree -RootNode $vRoot -SourcePath $f.FullName -DestParts $parts
                        }
                    }
                }

                # Process OTHER library files
                foreach ($f in $otherFiles) {
                    if ($f.FullName.StartsWith($source, [System.StringComparison]::InvariantCultureIgnoreCase)) {
                        $rel = $f.FullName.Substring($source.Length).TrimStart('\', '/')
                        $parts = $rel -split '[\\/]'
                        Add-ToVirtualTree -RootNode $vRoot -SourcePath $f.FullName -DestParts $parts
                    }
                }

                # Pre-seed Save folders after all ROMs (including Hacks) have populated the map
                Add-ToVirtualTree -RootNode $vRoot -DestParts @($osFolder, $saveSubDirBase) -FolderOnly
                Add-ToVirtualTree -RootNode $vRoot -DestParts @($osFolder, $rtcSubDirBase) -FolderOnly

                # Collect and match ALL saves (Main library + Hacks + GBCSYS Payload) in a single unified pass
                $allSaves = @($savFiles | Where-Object { $_.DirectoryName -notmatch '(?i)[\\/]SNAP$' })
                if (-not [string]::IsNullOrWhiteSpace($hacksSource) -and (Test-Path -LiteralPath $hacksSource)) {
                    $allSaves += @(Get-ChildItem -LiteralPath $hacksSource -File -Recurse | Where-Object { $_.Extension -match '(?i)^\.(sav|rtc|srm|fla)$' -and $_.DirectoryName -notmatch '(?i)[\\/]SNAP$' })
                }
                if (-not [string]::IsNullOrWhiteSpace($gbcSysPayload) -and (Test-Path -LiteralPath $gbcSysPayload)) {
                    $allSaves += @(Get-ChildItem -LiteralPath $gbcSysPayload -File -Recurse | Where-Object { $_.Extension -match '(?i)^\.(sav|rtc|srm|fla)$' -and $_.DirectoryName -notmatch '(?i)[\\/]SNAP$' })
                }

                foreach ($s in $allSaves) {
                    $finalExt = $s.Extension
                    $saveSubDir = if ($s.Extension -match '(?i)\.rtc$') { $rtcSubDirBase } else { $saveSubDirBase }
                    
                    # Normalize base name: Strip system folders and eager categories (GBC, GB, etc.)
                    # Match GBC before GB to avoid leaving "C" behind
                    $tempBase = $s.BaseName -replace '(?i)\.(gb|gbc)$', ''
                    $cleanBaseNoPrefix = $tempBase -replace '(?i)^(GBC|GB|GBA|EDGB|GBCSYS|GBOS|SAVE|RTC|SAVES)_*', ''
                    
                    if ([string]::IsNullOrWhiteSpace($cleanBaseNoPrefix)) { continue } 

                    $fuzzy = Get-FuzzyTitle -BaseName $cleanBaseNoPrefix
                    $matchedName = $null

                    if ($romNameMap.ContainsKey($fuzzy)) {
                        $matchedName = $romNameMap[$fuzzy]
                    }
                    else {
                        # Smart Fallback: Try stripping leading characters iteratively to resolve legacy prefixes (GBC, A-Z, doubled folders)
                        # We try stripping up to 20 characters to handle even long folder names prepended to the filename
                        for ($j = 1; $j -le 20; $j++) {
                            if ($cleanBaseNoPrefix.Length -gt ($j + 2)) {
                                $subBase = $cleanBaseNoPrefix.Substring($j)
                                $subFuzzy = Get-FuzzyTitle -BaseName $subBase
                                if ($romNameMap.ContainsKey($subFuzzy)) {
                                    $matchedName = $romNameMap[$subFuzzy]
                                    break
                                }
                            }
                        }
                    }

                    if ($matchedName) {
                        $finalSaveName = $matchedName + $finalExt
                        Add-ToVirtualTree -RootNode $vRoot -SourcePath $s.FullName -DestParts @($osFolder, $saveSubDir, $finalSaveName)
                    }
                    else {
                        $cleanOrphan = (Get-CleanRomName -BaseName $cleanBaseNoPrefix -PreserveTags:$chkKeepTags.Checked) + $finalExt
                        Add-ToVirtualTree -RootNode $vRoot -SourcePath $s.FullName -DestParts @($osFolder, $saveSubDir, $cleanOrphan)
                    }
                }

                Write-UiMsg "Virtual hierarchy built. Starting sequential sync..."
                
                $script:vTreeCount = 0
                $countAction = {
                    param($Node)
                    foreach ($c in $Node.Children) {
                        if ($c.IsFolder) { & $countAction $c } else { $script:vTreeCount++ }
                    }
                }
                & $countAction $vRoot
                $totalSyncNodes = $script:vTreeCount
                
                $nonSaves = @()
                if (-not [string]::IsNullOrWhiteSpace($gbcSysPayload) -and (Test-Path -LiteralPath $gbcSysPayload)) {
                    $nonSaves = @(Get-ChildItem -LiteralPath $gbcSysPayload -File -Recurse | Where-Object { $_.Extension -notmatch '(?i)^\.(sav|rtc|srm|fla)$' -or $_.DirectoryName -match '(?i)[\\/]SNAP$' })
                    $totalSyncNodes += $nonSaves.Count
                }
                
                $progressBar.Maximum = if ($totalSyncNodes -gt 0) { $totalSyncNodes } else { 1 }
                $progressBar.Value = 0

                # --- RENAME EXISTING SD SAVES TO MATCH ROM NAMES ---
                $sysPaths = @((Join-Path (Join-Path $dest $osFolder) $saveSubDirBase), (Join-Path (Join-Path $dest $osFolder) $rtcSubDirBase))
                foreach ($sp in $sysPaths) {
                    if (Test-Path -LiteralPath $sp) {
                        Write-UiMsg "Checking EverDrive system folder: $(Split-Path $sp -Leaf) for saves that need renaming..."
                        $existingSaves = Get-ChildItem -LiteralPath $sp -File
                        foreach ($s in $existingSaves) {
                            $cleanBaseNoPrefix = $s.BaseName -replace '(?i)^(GBC|GB|GBA|EDGB|GBCSYS|GBOS|SAVE|RTC|SAVES)_*', ''
                            if ([string]::IsNullOrWhiteSpace($cleanBaseNoPrefix)) { continue }

                            $fuzzy = Get-FuzzyTitle -BaseName $cleanBaseNoPrefix
                            $matchedName = $null
                            
                            if ($romNameMap.ContainsKey($fuzzy)) {
                                $matchedName = $romNameMap[$fuzzy]
                            }
                            else {
                                for ($j = 1; $j -le 20; $j++) {
                                    if ($cleanBaseNoPrefix.Length -gt ($j + 2)) {
                                        $subBase = $cleanBaseNoPrefix.Substring($j)
                                        $subFuzzy = Get-FuzzyTitle -BaseName $subBase
                                        if ($romNameMap.ContainsKey($subFuzzy)) {
                                            $matchedName = $romNameMap[$subFuzzy]
                                            break
                                        }
                                    }
                                }
                            }
                            
                            $finalName = if ($matchedName) { $matchedName } else { (Get-CleanRomName -BaseName $cleanBaseNoPrefix -PreserveTags:$chkKeepTags.Checked) }
                            $newFileName = $finalName + $s.Extension
                            
                            if ($s.Name -ine $newFileName) {
                                $newFilePath = Join-Path $s.DirectoryName $newFileName
                                if (-not (Test-Path -LiteralPath $newFilePath)) {
                                    Write-UiMsg " -> Renaming existing SD save: $($s.Name) to $newFileName"
                                    Rename-Item -LiteralPath $s.FullName -NewName $newFileName -Force
                                }
                            }
                        }
                        
                        # Purge subdirectories inside system folders (hardware doesn't support them)
                        $subDirs = Get-ChildItem -LiteralPath $sp -Directory
                        foreach ($sd in $subDirs) {
                            Write-UiMsg " -> Removing invalid subdirectory inside System Folder: $($sd.Name)"
                            Remove-Item -LiteralPath $sd.FullName -Recurse -Force -ErrorAction SilentlyContinue
                        }
                    }
                }

                Copy-VirtualTree -Node $vRoot -CurrentDestPath $dest -SdCatalog $sdCatalog

                # Directly copy non-save files from the GBCSYS Payload directly to the target OS Folder
                if (-not [string]::IsNullOrWhiteSpace($gbcSysPayload) -and (Test-Path -LiteralPath $gbcSysPayload)) {
                    Write-UiMsg "Copying non-save system files from GBCSYS Payload directly..."
                    foreach ($ns in $nonSaves) {
                        # Resolve relative path inside payload folder so subdirectories stay intact
                        $rel = $ns.FullName.Substring($gbcSysPayload.Length).TrimStart('\', '/')
                        # Drop everything directly into the real OS folder (e.g. EDGB or GBCSYS)
                        $targetSysPath = Join-Path (Join-Path $dest $osFolder) $rel
                        if (-not (Test-Path -LiteralPath (Split-Path $targetSysPath))) {
                            New-Item -ItemType Directory -Path (Split-Path $targetSysPath) | Out-Null
                        }
                        Copy-Item -LiteralPath $ns.FullName -Destination $targetSysPath -Force
                        Update-UiProgress
                    }
                }

            }
            else {
                # Standard bypass - Sync Source directly
                $bpFileCount = 0
                if ($sourceValid) { $bpFileCount += @(Get-ChildItem -LiteralPath $source -File -Recurse).Count }
                if (-not [string]::IsNullOrWhiteSpace($hacksSource) -and (Test-Path -LiteralPath $hacksSource)) { $bpFileCount += @(Get-ChildItem -LiteralPath $hacksSource -File -Recurse).Count }
                if (-not [string]::IsNullOrWhiteSpace($gbcSysPayload) -and (Test-Path -LiteralPath $gbcSysPayload)) { $bpFileCount += @(Get-ChildItem -LiteralPath $gbcSysPayload -File -Recurse).Count }
                
                $progressBar.Maximum = if ($bpFileCount -gt 0) { $bpFileCount } else { 1 }
                $progressBar.Value = 0

                if ($sourceValid) {
                    Write-UiMsg "Syncing main library directly..."
                    Copy-ItemsSorted -SrcPath $source -DestPath $dest
                }
                
                # --- FIX SUBDIRS IN BYPASS MODE ---
                $sysPaths = @((Join-Path (Join-Path $dest $osFolder) $saveSubDirBase), (Join-Path (Join-Path $dest $osFolder) $rtcSubDirBase))
                foreach ($sp in $sysPaths) {
                    if (Test-Path -LiteralPath $sp) {
                        $subDirs = Get-ChildItem -LiteralPath $sp -Directory
                        foreach ($sd in $subDirs) {
                            Write-UiMsg " -> Removing invalid subdirectory inside System Folder: $($sd.Name)"
                            Remove-Item -LiteralPath $sd.FullName -Recurse -Force -ErrorAction SilentlyContinue
                        }
                    }
                }

                # Sync Hacks directly
                if (-not [string]::IsNullOrWhiteSpace($hacksSource) -and (Test-Path -LiteralPath $hacksSource)) {
                    Write-UiMsg "Syncing ROM Hacks into root folder '[ROM Hacks]'..."
                    $hacksDest = Join-Path $dest "[ROM Hacks]"
                    $hackFilesRaw = @(Get-ChildItem -LiteralPath $hacksSource -File -Recurse | Where-Object { $_.Name -notmatch '(?i)^(\._|\.DS_Store)' -and $_.Extension -match '(?i)^\.gbc?$' })
                    
                    if ($chk1G1R.Checked) {
                        $hackFilesRaw = Get-BestRegionGames -Files $hackFilesRaw -USA:$chkRegionUSA.Checked -World:$chkRegionWorld.Checked -Eur:$chkRegionEur.Checked -Jpn:$chkRegionJpn.Checked
                    }

                    $hackGroups = Get-SeriesGroups -Files $hackFilesRaw
                    
                    foreach ($f in $hackFilesRaw) {
                        $destParts = @()
                        $group = $hackGroups[$f.FullName]
                        
                        if (-not [string]::IsNullOrWhiteSpace($group)) { $destParts += $group }
                        else {
                            if ($chkAZFolders.Checked) {
                                $cleanNameForAZ = Get-CleanRomName -BaseName $f.BaseName
                                $firstChar = if ($cleanNameForAZ.Length -gt 0) { $cleanNameForAZ.Substring(0, 1).ToUpper() } else { "#" }
                                if ($firstChar -match '[A-Z]') { $destParts += $firstChar } else { $destParts += "#" }
                            }
                        }
                        
                        $finalRomName = (Get-CleanRomName -BaseName $f.BaseName -PreserveTags:$chkKeepTags.Checked)
                        $targetHacksPath = $hacksDest
                        foreach ($p in $destParts) {
                            $targetHacksPath = Join-Path $targetHacksPath $p
                        }
                        
                        if (-not (Test-Path -LiteralPath $targetHacksPath)) { New-Item -ItemType Directory -Path $targetHacksPath | Out-Null }
                        Copy-Item -LiteralPath $f.FullName -Destination (Join-Path $targetHacksPath ($finalRomName + $f.Extension)) -Force
                    }

                    # Sync Hack Saves
                    $hackSaves = Get-ChildItem -LiteralPath $hacksSource -File -Recurse | Where-Object { $_.Extension -match '(?i)^\.(sav|rtc|srm|fla)$' -and $_.DirectoryName -notmatch '(?i)[\\/]SNAP$' }
                    foreach ($f in $hackSaves) {
                        $finalExt = $f.Extension
                        $saveSubDir = if ($f.Extension -match '(?i)\.rtc$') { $rtcSubDirBase } else { $saveSubDirBase }
                        $cleanBase = $f.BaseName -replace '(?i)\.(gb|gbc)$', ''
                        if ([string]::IsNullOrWhiteSpace($cleanBase)) { continue }
                        $finalRomCleanName = Get-CleanRomName -BaseName $cleanBase -PreserveTags:$chkKeepTags.Checked
                        $targetSavePath = Join-Path (Join-Path $dest $osFolder) $saveSubDir
                        if (-not (Test-Path -LiteralPath $targetSavePath)) { New-Item -ItemType Directory -Path $targetSavePath | Out-Null }
                        Copy-Item -LiteralPath $f.FullName -Destination (Join-Path $targetSavePath ($finalRomCleanName + $finalExt)) -Force
                    }
                }

                # Sync GBCSYS Payload directly
                if (-not [string]::IsNullOrWhiteSpace($gbcSysPayload) -and (Test-Path -LiteralPath $gbcSysPayload)) {
                    Write-UiMsg "Syncing GBCSYS Payload directly..."
                    # 1. Saves (With fuzzy-match renaming, extensions intact)
                    $payloadSaves = Get-ChildItem -LiteralPath $gbcSysPayload -File -Recurse | Where-Object { $_.Extension -match '(?i)^\.(sav|rtc|srm|fla)$' -and $_.DirectoryName -notmatch '(?i)[\\/]SNAP$' }
                    foreach ($f in $payloadSaves) {
                        $finalExt = $f.Extension
                        $saveSubDir = if ($f.Extension -match '(?i)\.rtc$') { $rtcSubDirBase } else { $saveSubDirBase }
                        $cleanBase = $f.BaseName -replace '(?i)\.(gb|gbc)$', ''
                        if ([string]::IsNullOrWhiteSpace($cleanBase)) { continue }
                        $finalRomCleanName = Get-CleanRomName -BaseName $cleanBase -PreserveTags:$chkKeepTags.Checked
                        $targetSavePath = Join-Path (Join-Path $dest $osFolder) $saveSubDir
                        if (-not (Test-Path -LiteralPath $targetSavePath)) { New-Item -ItemType Directory -Path $targetSavePath | Out-Null }
                        Copy-Item -LiteralPath $f.FullName -Destination (Join-Path $targetSavePath ($finalRomCleanName + $finalExt)) -Force
                    }
                    
                    # 2. Raw System Files (Direct replication)
                    $payloadSys = Get-ChildItem -LiteralPath $gbcSysPayload -File -Recurse | Where-Object { $_.Extension -notmatch '(?i)^\.(sav|rtc|srm|fla)$' -or $_.DirectoryName -match '(?i)[\\/]SNAP$' }
                    foreach ($ns in $payloadSys) {
                        $rel = $ns.FullName.Substring($gbcSysPayload.Length).TrimStart('\', '/')
                        $targetSysPath = Join-Path (Join-Path $dest $osFolder) $rel
                        if (-not (Test-Path -LiteralPath (Split-Path $targetSysPath))) {
                            New-Item -ItemType Directory -Path (Split-Path $targetSysPath) | Out-Null
                        }
                        Copy-Item -LiteralPath $ns.FullName -Destination $targetSysPath -Force
                    }
                }
            }

            Write-UiMsg "----------------------------------------"
            Write-UiMsg "Sync Complete!"
            Write-UiMsg "IMPORTANT: Safely eject your SD card before physically removing it."
            [System.Windows.Forms.MessageBox]::Show("Sync complete!`nYou can safely eject your SD card now.", "Success", 0, [System.Windows.Forms.MessageBoxIcon]::Information)
        }
        catch {
            $msg = "ERROR: $_"
            Write-UiMsg $msg
            [System.Windows.Forms.MessageBox]::Show($msg, "Error", 0, [System.Windows.Forms.MessageBoxIcon]::Error)
        }
        finally {
            if ($tempUnzipDir -and (Test-Path -LiteralPath $tempUnzipDir)) {
                Remove-Item -LiteralPath $tempUnzipDir -Recurse -Force -ErrorAction SilentlyContinue
            }

            $btnStart.Enabled = $true
            $txtSource.Enabled = $true
            $txtHacks.Enabled = $true
            $txtGbcSysPayload.Enabled = $true
            $txtDest.Enabled = $true
            $btnSource.Enabled = $true
            $btnHacks.Enabled = $true
            $btnGbcSysPayload.Enabled = $true
            $btnDest.Enabled = $true

            $chkGroup.Enabled = $true
            $chkTypeFolders.Enabled = $chkGroup.Checked
            $chkSeriesFolders.Enabled = $chkGroup.Checked
            $chk1G1R.Enabled = $true
            $chkZip.Enabled = $true
            $chkKeepTags.Enabled = $true
            $chkAZFolders.Enabled = $true
            $chkBackupSaves.Enabled = $true
            $chkRegionUSA.Enabled = $chk1G1R.Checked
            $chkRegionWorld.Enabled = $chk1G1R.Checked
            $chkRegionEur.Enabled = $chk1G1R.Checked
            $chkRegionJpn.Enabled = $chk1G1R.Checked
        }
    })
$form.Controls.Add($btnStart)

# Show the GUI
[void]$form.ShowDialog()
