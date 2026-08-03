[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [string]$WheelPath,

  [Parameter(Mandatory = $false)]
  [string]$ArchivePath
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$expectedWheelName = 'taxonomy_bench-0.3.0-py3-none-any.whl'
$wheelFullPath = (Resolve-Path $WheelPath).Path

if ([System.IO.Path]::GetFileName($wheelFullPath) -cne $expectedWheelName) {
  throw "Wheel filename must be $expectedWheelName."
}

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$wheelArchive = [System.IO.Compression.ZipFile]::OpenRead($wheelFullPath)
try {
  $metadataEntry = $wheelArchive.GetEntry('taxonomy_bench-0.3.0.dist-info/METADATA')
  if ($null -eq $metadataEntry) {
    throw 'Wheel must contain taxonomy_bench-0.3.0.dist-info/METADATA.'
  }
  $metadataReader = [System.IO.StreamReader]::new($metadataEntry.Open())
  try {
    $wheelMetadata = $metadataReader.ReadToEnd()
  } finally {
    $metadataReader.Dispose()
  }
} finally {
  $wheelArchive.Dispose()
}

if ($wheelMetadata -notmatch '(?m)^Name:\s*taxonomy-bench\s*$') {
  throw 'Wheel METADATA name must be taxonomy-bench.'
}
if ($wheelMetadata -notmatch '(?m)^Version:\s*0\.3\.0\s*$') {
  throw 'Wheel METADATA version must be 0.3.0.'
}

if (-not $ArchivePath) {
  $ArchivePath = Join-Path (Split-Path $projectRoot -Parent) 'taxonomy-bench.zip'
}

$releaseEntries = [ordered]@{
  '.gitignore' = Join-Path $projectRoot '.gitignore'
  'BENCHMARK_SPEC.md' = Join-Path $projectRoot 'BENCHMARK_SPEC.md'
  'LICENSE' = Join-Path $projectRoot 'LICENSE'
  'NOTICE.md' = Join-Path $projectRoot 'NOTICE.md'
  'README.md' = Join-Path $projectRoot 'README.md'
  'VALIDATION.md' = Join-Path $projectRoot 'VALIDATION.md'
  'dist/taxonomy_bench-0.3.0-py3-none-any.whl' = $wheelFullPath
  'pyproject.toml' = Join-Path $projectRoot 'pyproject.toml'
  'sample_data/dependencies.json' = Join-Path $projectRoot 'sample_data/dependencies.json'
  'sample_data/manifest.json' = Join-Path $projectRoot 'sample_data/manifest.json'
  'sample_data/topics.json' = Join-Path $projectRoot 'sample_data/topics.json'
  'scripts/package-release.ps1' = Join-Path $projectRoot 'scripts/package-release.ps1'
  'taxonomy_bench.py' = Join-Path $projectRoot 'taxonomy_bench.py'
  'taxonomy_bench_cli.py' = Join-Path $projectRoot 'taxonomy_bench_cli.py'
  'taxonomy_bench_progression.py' = Join-Path $projectRoot 'taxonomy_bench_progression.py'
  'taxonomy_bench_protocol.py' = Join-Path $projectRoot 'taxonomy_bench_protocol.py'
  'taxonomy_bench_report.py' = Join-Path $projectRoot 'taxonomy_bench_report.py'
  'taxonomy_bench_wave.py' = Join-Path $projectRoot 'taxonomy_bench_wave.py'
  'tests/test_progression.py' = Join-Path $projectRoot 'tests/test_progression.py'
  'tests/test_report_html.py' = Join-Path $projectRoot 'tests/test_report_html.py'
  'tests/test_subscription_cli.py' = Join-Path $projectRoot 'tests/test_subscription_cli.py'
  'tests/test_taxonomy_bench.py' = Join-Path $projectRoot 'tests/test_taxonomy_bench.py'
  'tests/test_wave_controller.py' = Join-Path $projectRoot 'tests/test_wave_controller.py'
}

foreach ($sourcePath in $releaseEntries.Values) {
  if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
    throw "Release source does not exist: $sourcePath"
  }
}

$checksumPath = Join-Path $projectRoot 'SHA256SUMS'
$checksumLines = foreach ($archiveRelativePath in $releaseEntries.Keys) {
  $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $releaseEntries[$archiveRelativePath]).Hash.ToLowerInvariant()
  "$hash  $archiveRelativePath"
}
[System.IO.File]::WriteAllLines(
  $checksumPath,
  [string[]]$checksumLines,
  [System.Text.UTF8Encoding]::new($false)
)

$verifiedPaths = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
foreach ($checksumLine in [System.IO.File]::ReadAllLines($checksumPath)) {
  if ($checksumLine -notmatch '^([0-9a-f]{64})  (.+)$') {
    throw "Malformed checksum line: $checksumLine"
  }

  $expectedHash = $Matches[1]
  $archiveRelativePath = $Matches[2]
  if (-not $releaseEntries.Contains($archiveRelativePath)) {
    throw "Checksum references an unmapped release path: $archiveRelativePath"
  }
  if (-not $verifiedPaths.Add($archiveRelativePath)) {
    throw "Duplicate checksum path: $archiveRelativePath"
  }

  $actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $releaseEntries[$archiveRelativePath]).Hash.ToLowerInvariant()
  if ($actualHash -ne $expectedHash) {
    throw "Checksum mismatch for $archiveRelativePath"
  }
}

if ($verifiedPaths.Count -ne $releaseEntries.Count) {
  throw "Expected $($releaseEntries.Count) verified checksums, found $($verifiedPaths.Count)."
}

$archiveFullPath = [System.IO.Path]::GetFullPath($ArchivePath)
$archiveParent = Split-Path $archiveFullPath -Parent
if (-not (Test-Path -LiteralPath $archiveParent -PathType Container)) {
  throw "Archive parent directory does not exist: $archiveParent"
}
$newArchivePath = "$archiveFullPath.new"
$fixedTimestamp = [System.DateTimeOffset]::new(1980, 1, 1, 0, 0, 0, [System.TimeSpan]::Zero)

$archiveStream = [System.IO.File]::Open(
  $newArchivePath,
  [System.IO.FileMode]::Create,
  [System.IO.FileAccess]::Write,
  [System.IO.FileShare]::None
)
try {
  $zipArchive = [System.IO.Compression.ZipArchive]::new(
    $archiveStream,
    [System.IO.Compression.ZipArchiveMode]::Create,
    $false
  )
  try {
    $archiveSources = [ordered]@{}
    foreach ($archiveRelativePath in $releaseEntries.Keys) {
      $archiveSources[$archiveRelativePath] = $releaseEntries[$archiveRelativePath]
    }
    $archiveSources['SHA256SUMS'] = $checksumPath

    foreach ($archiveRelativePath in $archiveSources.Keys) {
      $entryName = "taxonomy-bench/$archiveRelativePath"
      $entry = $zipArchive.CreateEntry($entryName, [System.IO.Compression.CompressionLevel]::Optimal)
      $entry.LastWriteTime = $fixedTimestamp
      $entryStream = $entry.Open()
      $sourceStream = [System.IO.File]::OpenRead($archiveSources[$archiveRelativePath])
      try {
        $sourceStream.CopyTo($entryStream)
      } finally {
        $sourceStream.Dispose()
        $entryStream.Dispose()
      }
    }
  } finally {
    $zipArchive.Dispose()
  }
} finally {
  $archiveStream.Dispose()
}

[System.IO.File]::Move($newArchivePath, $archiveFullPath, $true)

$expectedEntries = @(
  $releaseEntries.Keys | ForEach-Object { "taxonomy-bench/$_" }
) + 'taxonomy-bench/SHA256SUMS'
$expectedEntries = @($expectedEntries | Sort-Object)

$readArchive = [System.IO.Compression.ZipFile]::OpenRead($archiveFullPath)
try {
  $actualEntries = @($readArchive.Entries | ForEach-Object FullName | Sort-Object)
} finally {
  $readArchive.Dispose()
}

if (($actualEntries.Count -ne $expectedEntries.Count) -or
    (($actualEntries -join "`n") -ne ($expectedEntries -join "`n"))) {
  throw "Archive entry set does not match the release mapping."
}
if ($actualEntries -match 'taxonomy_bench-0\.1\.0') {
  throw 'Archive contains a taxonomy-bench 0.1.0 wheel.'
}

Write-Output "Verified $($verifiedPaths.Count) SHA-256 checksums."
Write-Output "Created $archiveFullPath with $($actualEntries.Count) exact entries."
