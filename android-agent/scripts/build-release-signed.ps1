param(
    [string]$SigningStore = "$env:USERPROFILE\.screentimefx-android\release-signing.dpapi.json",
    [string]$Output = "",
    [switch]$SkipBuild,
    [switch]$Offline
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$config = Get-Content -LiteralPath (Join-Path $root "app\build.gradle.kts") -Raw
$version = [regex]::Match($config, 'versionName\s*=\s*"(\d+\.\d+\.\d+)"').Groups[1].Value
$versionCode = [regex]::Match($config, 'versionCode\s*=\s*(\d+)').Groups[1].Value
if (-not $version -or -not $versionCode) { throw "ANDROID_VERSION_CONFIG_INVALID" }
if (-not $Output) { $Output = Join-Path $root "build\release\StoryFX-Android-$version-v$versionCode.apk" }
if (-not (Test-Path -LiteralPath $SigningStore -PathType Leaf)) { throw "SIGNING_STORE_MISSING" }
$java = "C:\Program Files\Android\Android Studio1\jbr\bin\java.exe"
if (-not (Test-Path -LiteralPath $java)) { throw "JAVA_RUNTIME_MISSING" }
$sdk = Join-Path $env:LOCALAPPDATA "Android\Sdk"
$signer = Join-Path $sdk "build-tools\35.0.0\lib\apksigner.jar"
$aapt = Join-Path $sdk "build-tools\35.0.0\aapt.exe"
if (-not (Test-Path -LiteralPath $signer) -or -not (Test-Path -LiteralPath $aapt)) {
    throw "ANDROID_SDK_TOOL_MISSING"
}
if (-not $SkipBuild) {
    $arguments = @("-classpath", (Join-Path $root "gradle\wrapper\gradle-wrapper.jar"),
        "org.gradle.wrapper.GradleWrapperMain", "-p", $root, "--no-daemon", "--no-problems-report")
    if ($Offline) { $arguments += "--offline" }
    $arguments += @(':app:testDebugUnitTest', ':app:lintDebug', ':app:assembleDebug', ':app:assembleRelease')
    & $java @arguments
    if ($LASTEXITCODE -ne 0) { throw "ANDROID_BUILD_GATE_FAILED" }
}
$unsigned = Join-Path $root "app\build\outputs\apk\release\app-release-unsigned.apk"
if (-not (Test-Path -LiteralPath $unsigned -PathType Leaf)) { throw "UNSIGNED_CANDIDATE_MISSING" }
$secret = Get-Content -LiteralPath $SigningStore -Raw | ConvertFrom-Json
if (-not (Test-Path -LiteralPath $secret.storeFile -PathType Leaf)) { throw "SIGNING_KEYSTORE_MISSING" }
function Unseal([string]$value) {
    $secure = ConvertTo-SecureString $value
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr); $secure.Dispose() }
}
New-Item -ItemType Directory -Path (Split-Path -Parent $Output) -Force | Out-Null
try {
    $env:STORYFX_RELEASE_STORE_PASSWORD = Unseal $secret.storePasswordDpapi
    $env:STORYFX_RELEASE_KEY_PASSWORD = Unseal $secret.keyPasswordDpapi
    & $java -jar $signer sign --ks $secret.storeFile --ks-key-alias $secret.keyAlias `
        --ks-pass env:STORYFX_RELEASE_STORE_PASSWORD --key-pass env:STORYFX_RELEASE_KEY_PASSWORD `
        --out $Output $unsigned
    if ($LASTEXITCODE -ne 0) { throw "ANDROID_SIGN_FAILED" }
    $report = & $java -jar $signer verify --verbose --print-certs $Output
    if ($LASTEXITCODE -ne 0) { throw "ANDROID_SIGNATURE_INVALID" }
    $certificate = [regex]::Match(($report -join "`n"),
        'Signer #1 certificate SHA-256 digest: ([a-fA-F0-9]{64})').Groups[1].Value.ToLowerInvariant()
    if ($certificate -ne "e3795a1bca6acab02ce61b724ef827c35c19a2c4ffbbb7d9c4c3af3fa7009a12") {
        throw "ANDROID_SIGNING_CERTIFICATE_CHANGED"
    }
    $badging = (& $aapt dump badging $Output) -join "`n"
    if ($LASTEXITCODE -ne 0 -or $badging -notmatch "package: name='com\.formafx\.storyfx\.agent'" -or
        $badging -notmatch "versionCode='$versionCode'" -or $badging -notmatch "versionName='$version'") {
        throw "ANDROID_RELEASE_IDENTITY_MISMATCH"
    }
    if ($badging -match 'READ_MEDIA_AUDIO|MANAGE_EXTERNAL_STORAGE|RECORD_AUDIO|CAMERA|ACCESS_FINE_LOCATION|ACCESS_COARSE_LOCATION|SYSTEM_ALERT_WINDOW|QUERY_ALL_PACKAGES') {
        throw "ANDROID_UNEXPECTED_SENSITIVE_PERMISSION"
    }
    $allowed = @('android.permission.INTERNET', 'android.permission.REQUEST_INSTALL_PACKAGES',
        'android.permission.RECEIVE_BOOT_COMPLETED', 'android.permission.WAKE_LOCK',
        'android.permission.READ_MEDIA_IMAGES', 'android.permission.READ_MEDIA_VIDEO', 'android.permission.READ_EXTERNAL_STORAGE',
        'com.formafx.storyfx.agent.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION',
        'android.permission.ACCESS_NETWORK_STATE', 'android.permission.FOREGROUND_SERVICE')
    $permissions = [regex]::Matches($badging, "uses-permission[^:]*: name='([^']+)'")
    foreach ($permission in $permissions) {
        if ($permission.Groups[1].Value -notin $allowed) { throw "ANDROID_PERMISSION_OUTSIDE_ALLOWLIST" }
    }
    [xml]$manifest = Get-Content -LiteralPath (Join-Path $root 'app\src\main\AndroidManifest.xml') -Raw
    $androidNamespace = 'http://schemas.android.com/apk/res/android'
    $publicationService = @($manifest.manifest.application.service | Where-Object {
        $_.GetAttribute('name', $androidNamespace) -eq '.publication.PublicationService' })
    if ($publicationService.Count -ne 1 -or
        $publicationService[0].GetAttribute('permission', $androidNamespace) -ne 'android.permission.BIND_ACCESSIBILITY_SERVICE') {
        throw 'ANDROID_ACCESSIBILITY_BINDING_UNPROTECTED'
    }
    $result = [ordered]@{ version = $version; version_code = [int]$versionCode;
        package = "com.formafx.storyfx.agent"; signed_apk = $Output;
        sha256 = (Get-FileHash -LiteralPath $Output -Algorithm SHA256).Hash.ToLowerInvariant();
        certificate_sha256 = $certificate; bytes = (Get-Item -LiteralPath $Output).Length;
        apk_signature_verified = $true; release_identity_verified = $true;
        password_logged = $false; token_logged = $false; secrets_logged = $false }
    $result | ConvertTo-Json | Set-Content -LiteralPath "$Output.manifest.json" -Encoding UTF8
    Write-Output "signed_apk=$Output"
    Write-Output "sha256=$($result.sha256)"
    Write-Output "certificate_sha256=$certificate"
    Write-Output "signature_verified=true; package_verified=true; secrets_logged=false"
} finally {
    Remove-Item Env:STORYFX_RELEASE_STORE_PASSWORD, Env:STORYFX_RELEASE_KEY_PASSWORD -ErrorAction SilentlyContinue
    $secret = $null
}
