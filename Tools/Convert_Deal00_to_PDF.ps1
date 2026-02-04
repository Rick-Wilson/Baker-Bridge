# Define source and destination folders
$sourceRoot = "B:\Website\Baker Bridge\bakerbridge.coffeecup.com"
$destFolder = "B:\Tools\pdfs"

# Ensure the destination folder exists
if (!(Test-Path -Path $destFolder)) {
    New-Item -Path $destFolder -ItemType Directory | Out-Null
}

# Path to wkhtmltopdf executable
$wkhtmltopdf = "C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf"

# Get all deal00.html files recursively from the source root
Get-ChildItem -Path $sourceRoot -Filter "deal00.html" -Recurse | ForEach-Object {

    # Full path to the current HTML file
    $htmlFile = $_.FullName

    # Get the relative directory path (if the file is directly under the root, set to "root")
    $relativePath = $_.DirectoryName.Substring($sourceRoot.Length).TrimStart("\")
    if ([string]::IsNullOrEmpty($relativePath)) {
        $pdfName = "root.pdf"
    }
    else {
        # Replace any nested folder separators with underscores and append .pdf extension
        $pdfName = ($relativePath -replace "\\", "_") + ".pdf"
    }

    # Create the full path for the output PDF
    $pdfFile = Join-Path $destFolder $pdfName

    Write-Output "Converting '$htmlFile' to '$pdfFile'"

    # Run the conversion command (using the original file path)
    & "$wkhtmltopdf" --page-size Letter --quiet "$htmlFile" --print-media-type "$pdfFile"

    # Add a half-second delay after each conversion
    Start-Sleep -Milliseconds 500
}