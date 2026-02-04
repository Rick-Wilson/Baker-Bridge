# Define the folder containing the .pbn files
$sourceFolder = "B:\Tools\pbns"

# Retrieve the root folder and all subfolders, sorted alphabetically by full path
$folders = @(Get-Item $sourceFolder) + (Get-ChildItem -Path $sourceFolder -Directory -Recurse | Sort-Object FullName)

foreach ($folder in $folders | Sort-Object FullName) {
    Write-Output "Processing folder: $($folder.FullName)"
    
    # Get all .pbn files in the current folder, sorted alphabetically by name
    $pbnFiles = Get-ChildItem -Path $folder.FullName -Filter "*.pbn" | Sort-Object Name
    
    foreach ($pbnFile in $pbnFiles) {
        Write-Output "Converting $($pbnFile.FullName) to PDF..."
        # Run the conversion command using the SavePDF.js script
        cscript /nologo S:\SavePDF.js $pbnFile.FullName
    }
}