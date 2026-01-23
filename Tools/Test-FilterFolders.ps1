function Filter-Folders {
    param (
        [Parameter(Mandatory = $true)]
        [string]$Filter
    )

    $baseDir = Join-Path -Path (Get-Location) -ChildPath "Presentation"
    if (-not (Test-Path $baseDir)) {
        throw "Error: 'Presentation' folder not found in the current directory."
    }

    $exclude = $false
    $pattern = $Filter

    if ($pattern.StartsWith("-")) {
        $exclude = $true
        $pattern = $pattern.Substring(1)
    }

    if ([string]::IsNullOrWhiteSpace($pattern)) {
        $pattern = "*"
    } elseif (-not $pattern.Contains("*")) {
        $pattern = "*$pattern*"
    }

    function Get-LeafFolders {
        param (
            [string]$Path
        )

        $dirs = Get-ChildItem -Path $Path -Directory | Sort-Object Name
        if ($dirs.Count -eq 0) {
            return ,$Path
        }

        $leaves = @()
        foreach ($dir in $dirs) {
            $leaves += Get-LeafFolders -Path $dir.FullName
        }
        return $leaves
    }

    $leafFolders = Get-LeafFolders -Path $baseDir
    $result = @()

    foreach ($fullPath in $leafFolders) {
        $relative = $fullPath.Substring($baseDir.Length + 1)
        $folderName = Split-Path $relative -Leaf

        $matches = $folderName -like $pattern

        if (($exclude -and -not $matches) -or (-not $exclude -and $matches)) {
            $result += $relative
        }
    }

    return $result
}

# --- Test Harness ---

if ($args.Count -ne 1) {
    Write-Host "Usage: .\rotate_lesson_collection.ps1 <filter>"
    Write-Host 'Example: .\rotate_lesson_collection.ps1 "*math*"'
    exit 1
}

try {
    $results = Filter-Folders -Filter $args[0]
    Write-Host "`nMatching leaf folders:"
    foreach ($folder in $results) {
        Write-Host $folder
    }
} catch {
    Write-Error $_
    exit 2
}