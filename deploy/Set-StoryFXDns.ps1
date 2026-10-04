param([switch]$Apply)
$ErrorActionPreference = 'Stop'
$zone = '195cf9c895ecb9eef321ad90e7114e25'
$name = 'story.formafx.com'
$address = '157.180.96.245'
$backupDir = Join-Path (Split-Path $PSScriptRoot -Parent) '.runtime\deploy'
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
. 'C:\FormaFX_Server_Exports\_tools\load_formafx_cloudflare_env.ps1' | Out-Null
try {
  if ($env:CLOUDFLARE_ACCOUNT_ID -ne 'f30c8a6078a1c26537ff7b94307fbd1d') { throw 'ACCOUNT_REFUSED' }
  $headers = @{ Authorization = 'Bearer ' + $env:CLOUDFLARE_API_TOKEN }
  $base = 'https://api.cloudflare.com/client/v4/zones/' + $zone
  $zoneInfo = Invoke-RestMethod -Uri $base -Headers $headers
  if (-not $zoneInfo.success -or $zoneInfo.result.name -ne 'formafx.com') { throw 'ZONE_REFUSED' }
  $uri = $base + '/dns_records?name=' + $name
  $before = Invoke-RestMethod -Uri $uri -Headers $headers
  if (-not $before.success) { throw 'DNS_READ_FAILED' }
  $records = @($before.result)
  $backup = Join-Path $backupDir ('story-dns-before-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.json')
  $records | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $backup -Encoding UTF8
  if ($records.Count -gt 1) { throw 'MULTIPLE_STORY_RECORDS_REFUSED' }
  if ($records.Count -eq 1 -and ($records[0].type -ne 'A' -or $records[0].content -ne $address)) {
    throw 'EXISTING_STORY_RECORD_DIFFERS'
  }
  if ($Apply -and $records.Count -eq 0) {
    $body = @{type='A'; name=$name; content=$address; ttl=1; proxied=$false} | ConvertTo-Json
    $result = Invoke-RestMethod -Uri ($base + '/dns_records') -Method Post -Headers $headers -ContentType 'application/json' -Body $body
    if (-not $result.success) { throw 'DNS_WRITE_FAILED' }
    @{id=$result.result.id; name=$name; created=$true} | ConvertTo-Json | Set-Content (Join-Path $backupDir 'story-dns-receipt.json')
    Write-Output 'dns_modified=true'
  } else { Write-Output 'dns_modified=false' }
  $after = Invoke-RestMethod -Uri $uri -Headers $headers
  Write-Output ('story_dns_records=' + @($after.result).Count)
  Write-Output ('story_dns_target_verified=' + [bool](@($after.result | Where-Object { $_.type -eq 'A' -and $_.content -eq $address }).Count -eq 1))
  Write-Output ('backup=' + $backup)
} finally {
  $env:CLOUDFLARE_API_TOKEN = $null
  $env:CF_API_TOKEN = $null
  $env:CLOUDFLARE_ACCOUNT_ID = $null
  $env:CF_ACCOUNT_ID = $null
}
