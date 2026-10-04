[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$taskDirectory = Join-Path (Split-Path -Parent $PSScriptRoot) '.runtime\private'
$taskSecretPath = Join-Path $taskDirectory 'work-login.dpapi'
New-Item -ItemType Directory -Path $taskDirectory -Force | Out-Null
Write-Host 'Compte de validation FormaFX autorisé pour cette tâche'
$taskPassword = Read-Host 'Mot de passe (saisie masquée)' -AsSecureString
if ($taskPassword.Length -eq 0) { throw 'Mot de passe vide : aucune sauvegarde.' }
$taskCipher = ConvertFrom-SecureString $taskPassword
[IO.File]::WriteAllText($taskSecretPath, $taskCipher, [Text.UTF8Encoding]::new($false))
$taskIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
$taskAcl = [Security.AccessControl.FileSecurity]::new()
$taskAcl.SetOwner($taskIdentity.User)
$taskAcl.SetAccessRuleProtection($true, $false)
foreach ($taskSid in @($taskIdentity.User, [Security.Principal.SecurityIdentifier]::new('S-1-5-18'))) {
  $taskAcl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
    $taskSid, [Security.AccessControl.FileSystemRights]::FullControl, 'Allow'))
}
Set-Acl -LiteralPath $taskSecretPath -AclObject $taskAcl
Remove-Variable taskPassword, taskCipher
Write-Host 'Coffre DPAPI enregistré. Le mot de passe ne sera pas affiché.'
