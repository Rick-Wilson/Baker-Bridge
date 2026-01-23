# Define file paths
$missingBidsPath     = "missing_bids.csv"
$auctionTemplatePath = "auction_templates.dlr"
$csvOutputFile       = "constructed_hands.csv"

# Write CSV header row with capitalized Subfolder and Deal.
$csvHeader = "Subfolder,Deal,NorthHand,EastHand,SouthHand,WestHand,label"
Set-Content -Path $csvOutputFile -Value $csvHeader

# Function to convert a period-delimited hand string (Spades.Hearts.Diamonds.Clubs)
# into the format: S:{cards} H:{cards} D:{cards} C:{cards}
function Format-Hand {
    param(
        [string]$handString
    )
    $suits = $handString -split "\."
    if ($suits.Length -eq 4) {
        return "S:$($suits[0]) H:$($suits[1]) D:$($suits[2]) C:$($suits[3])"
    }
    else {
        Write-Warning "Hand string '$handString' does not have 4 parts; leaving it unchanged."
        return $handString
    }
}

# Read the missing bids CSV and auction templates file.
# Force auction templates to lowercase to match the label.
$missingBids      = Import-Csv -Path $missingBidsPath
$auctionTemplates = (Get-Content -Path $auctionTemplatePath -Raw).ToLower()

# Initialize the list for unsupported bid sequences and the counter for unprocessed hands.
$unsupported_bid_sequences = @()
$unprocessed_hands = 0

# Set maximum supported hands to process.
$max_hands = 5000
$supported_hands = 0

# Process each row in the missing bids file.
foreach ($row in $missingBids) {
    # Get the bid sequence.
    $bidSequence = $row.bidsequence

    # If Bid is empty, use "auction_calm" as the label; otherwise, construct the label normally.
    if ([string]::IsNullOrEmpty($bidSequence)) {
        $label = "auction_calm"
    }
    else {
        $modifiedBidSequence = $bidSequence -replace "-", "_"
        $label = ("auction_" + $modifiedBidSequence).ToLower()
    }
    
    # Check if the label is present in the auction templates file.
    if ($auctionTemplates -notmatch $label) {
        # Only add unique bid sequences.
        if (-not ($unsupported_bid_sequences -contains $bidSequence)) {
            $unsupported_bid_sequences += $bidSequence
        }
        $unprocessed_hands++
    }
    else {
        # Create a local copy of the auction templates content.
        $templateContent = $auctionTemplates
        # If the input Seat is East, swap East and West references in the template content.
        if ($row.Seat -eq "East") {
            $templateContent = $templateContent -replace "east", "__TEMP__"
            $templateContent = $templateContent -replace "west", "east"
            $templateContent = $templateContent -replace "__TEMP__", "west"
        }
        
        # For file naming, replace slashes (both forward and backward) in subfolder with underscores.
        $sanitizedSubfolder = $row.subfolder -replace '[\\/]', '_'
        
        # Create a temporary dealer script file using the sanitized subfolder and deal.
        $tempFileName = "$sanitizedSubfolder`_Deal_$($row.deal).dlr"
        
        # Build the content for the temp file.
        $fileContent = @()
        $fileContent += "produce 1"
        # Add row 2.
        $fileContent += "generate 100000"
        # Append the (possibly swapped) auction template content.
        $fileContent += $templateContent.Split("`n")
        foreach ($hand in @("North", "East", "South", "West")) {
            $handKey = "${hand}Hand"
            if ($row.$handKey -and $row.$handKey.Trim() -ne "") {
                $cards = $row.$handKey
                # Convert spaces to commas, then remove colons.
                $cards = $cards -replace " ", ","
                $cards = $cards -replace ":", ""
                $fileContent += "predeal $($hand.ToLower()) $cards"
            }
        }
        $fileContent += "condition $label"
        $fileContent += "action printoneline"
        
        $finalContent = $fileContent -join "`n"
        Set-Content -Path $tempFileName -Value $finalContent
        
        # Commented informational messages:
        # Write-Host "Created temporary file: $tempFileName"
        
        # Capture the output from dealer into a temporary output file.
        $outputTempFile = [System.IO.Path]::GetTempFileName()
        # Write-Host "Executing dealer on $tempFileName..."
        & dealer $tempFileName | Out-File -FilePath $outputTempFile -Encoding UTF8
        
        # Read the first line of the dealer output.
        $dealerOutputLines = Get-Content -Path $outputTempFile
        $firstLine = $dealerOutputLines[0]
        
        if ($firstLine -like "n *") {
            # Parse the dealer output assuming format:
            # n {northhands} e {easthands} s {southhands} w {westhands}
            $pattern = '^n\s*(?<north>.*?)\s*e\s*(?<east>.*?)\s*s\s*(?<south>.*?)\s*w\s*(?<west>.*)$'
            $match = [regex]::Match($firstLine, $pattern)
            if ($match.Success) {
                $northHandRaw = $match.Groups["north"].Value.Trim()
                $eastHandRaw  = $match.Groups["east"].Value.Trim()
                $southHandRaw = $match.Groups["south"].Value.Trim()
                $westHandRaw  = $match.Groups["west"].Value.Trim()
                
                # Convert each hand from period-delimited format to "S:cards H:cards D:cards C:cards"
                $northHand = Format-Hand $northHandRaw
                $eastHand  = Format-Hand $eastHandRaw
                $southHand = Format-Hand $southHandRaw
                $westHand  = Format-Hand $westHandRaw
                
                # Construct CSV line with original subfolder (with slashes), deal, four hand fields, and label.
                $csvLine = "$($row.subfolder),$($row.deal),$northHand,$eastHand,$southHand,$westHand,$label"
                # Commented out CSV display to standard output:
                # Write-Output $csvLine
                $csvLine | Out-File -FilePath $csvOutputFile -Append -Encoding UTF8
                
                # Delete the temporary dealer script file on success.
                Remove-Item $tempFileName -Force
            }
            else {
                Write-Error "Error: Could not parse dealer output '$firstLine' for subfolder $($row.subfolder), deal $($row.deal), label $label."
            }
        }
        else {
            Write-Error "Error: dealer output does not start with 'n ' for subfolder $($row.subfolder), deal $($row.deal), label $label. Output: $firstLine"
        }
        
        # Clean up the temporary output file.
        # Remove-Item $outputTempFile -Force
        
        $supported_hands++
        if ($supported_hands -ge $max_hands) {
            Write-Host "Reached maximum supported hands ($max_hands). Exiting loop."
            break
        }
    }
}

Write-Host "Unsupported bid sequences:" $unsupported_bid_sequences
Write-Host "Total unprocessed hands:" $unprocessed_hands
Write-Host "Successfully processed $supported_hands supported hands."