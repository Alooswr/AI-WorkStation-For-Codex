[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$BinPath,

    [Parameter(Mandatory = $true)]
    [string]$HexPath,

    [Parameter(Mandatory = $true)]
    [string]$DestinationDirectory,

    [Parameter(Mandatory = $true)]
    [string]$OrgPrefix,

    [Parameter(Mandatory = $true)]
    [string]$ProductModel,

    [Parameter(Mandatory = $true)]
    [string]$Role,

    [Parameter(Mandatory = $true)]
    [string]$Chip,

    [Parameter(Mandatory = $true)]
    [ValidateSet('Release', 'Demo')]
    [string]$SoftwareType,

    [Parameter(Mandatory = $true)]
    [string]$Version,

    [Parameter(Mandatory = $true)]
    [string]$ReleaseDate,

    [string]$SpecialApprovalId
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-NormalizedToken {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value,

        [Parameter(Mandatory = $true)]
        [string]$FieldName
    )

    $token = $Value.Trim() -replace '\s+', ''
    if ([string]::IsNullOrWhiteSpace($token) -or $token -notmatch '^[A-Za-z0-9.-]+$') {
        throw "$FieldName must contain only letters, digits, periods, or hyphens and cannot be empty."
    }

    return $token
}

function Get-SourceFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [string]$ExpectedExtension
    )

    $item = Get-Item -LiteralPath $Path
    if ($item.PSIsContainer) {
        throw "Source is not a file: $Path"
    }
    if ($item.Extension -ine $ExpectedExtension) {
        throw "Expected a $ExpectedExtension file: $Path"
    }
    if ($item.Length -le 0) {
        throw "Source file is empty: $Path"
    }

    return $item
}

$bin = Get-SourceFile -Path $BinPath -ExpectedExtension '.bin'
$hex = Get-SourceFile -Path $HexPath -ExpectedExtension '.hex'
$destinationItem = Get-Item -LiteralPath $DestinationDirectory
if (-not $destinationItem.PSIsContainer) {
    throw "Destination is not a directory: $DestinationDirectory"
}

$hexFirst = Get-Content -LiteralPath $hex.FullName -TotalCount 1
$hexLast = Get-Content -LiteralPath $hex.FullName -Tail 1
if ($hexFirst -notmatch '^:' -or $hexLast.Trim() -ne ':00000001FF') {
    throw "HEX file does not have a valid Intel HEX start and EOF record: $($hex.FullName)"
}

$prefixToken = Get-NormalizedToken -Value $OrgPrefix -FieldName 'OrgPrefix'
$model = $ProductModel.Trim()
$model = $model -replace '[^A-Za-z0-9]', ''
if ([string]::IsNullOrWhiteSpace($model)) {
    throw 'ProductModel is empty after normalization.'
}
$productToken = $prefixToken.ToUpperInvariant() + $model.ToUpperInvariant()
$roleToken = Get-NormalizedToken -Value $Role -FieldName 'Role'
$chipToken = Get-NormalizedToken -Value $Chip -FieldName 'Chip'

$versionToken = $Version.Trim()
if ($versionToken -match '^(?i:V)') {
    $versionToken = 'V' + $versionToken.Substring(1)
} else {
    $versionToken = 'V' + $versionToken
}
if ($versionToken -notmatch '^V[0-9]+(?:\.[A-Za-z0-9-]+)*$') {
    throw 'Version must look like V1.0.0 and cannot contain underscores.'
}

$parsedDate = [datetime]::MinValue
$validDate = [datetime]::TryParseExact(
    $ReleaseDate,
    'yyyyMMdd',
    [Globalization.CultureInfo]::InvariantCulture,
    [Globalization.DateTimeStyles]::None,
    [ref]$parsedDate
)
if (-not $validDate) {
    throw 'ReleaseDate must be a real date in yyyyMMdd format.'
}

$approvalSuffix = ''
if (-not [string]::IsNullOrWhiteSpace($SpecialApprovalId)) {
    $approvalToken = Get-NormalizedToken -Value $SpecialApprovalId -FieldName 'SpecialApprovalId'
    $approvalSuffix = '_' + $approvalToken
}

$softwareTypeToken = if ($SoftwareType -ieq 'Release') { 'Release' } else { 'Demo' }
$baseName = '{0}_{1}_{2}_{3}_{4}_{5}{6}' -f `
    $productToken, $roleToken, $chipToken, $softwareTypeToken, $versionToken, $ReleaseDate, $approvalSuffix

$destinationRoot = [IO.Path]::GetFullPath($destinationItem.FullName).TrimEnd('\')
$plans = @(
    [pscustomobject]@{ Source = $bin; Name = "$baseName.bin" },
    [pscustomobject]@{ Source = $hex; Name = "$baseName.hex" }
)

$results = foreach ($plan in $plans) {
    $destinationPath = [IO.Path]::GetFullPath((Join-Path $destinationRoot $plan.Name))
    $destinationParent = [IO.Path]::GetDirectoryName($destinationPath).TrimEnd('\')
    if (-not $destinationParent.Equals($destinationRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Destination escaped the selected archive directory: $destinationPath"
    }

    $sourceHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $plan.Source.FullName).Hash
    $status = 'Copied'
    if (Test-Path -LiteralPath $destinationPath) {
        $destinationHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $destinationPath).Hash
        if ($destinationHash -ne $sourceHash) {
            throw "Destination exists with different content: $destinationPath"
        }
        $status = 'AlreadyPresent'
    } else {
        Copy-Item -LiteralPath $plan.Source.FullName -Destination $destinationPath
        $destinationHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $destinationPath).Hash
        if ($destinationHash -ne $sourceHash) {
            throw "SHA-256 mismatch after copy: $destinationPath"
        }
    }

    $destinationFile = Get-Item -LiteralPath $destinationPath
    [pscustomobject]@{
        Status      = $status
        Source      = $plan.Source.FullName
        Destination = $destinationFile.FullName
        Length      = $destinationFile.Length
        SHA256      = $sourceHash
    }
}

$results
