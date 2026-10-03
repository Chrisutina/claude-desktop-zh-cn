# Run: powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests/test_windows.ps1
# Load function definitions only; never invoke the installer or real user configuration.
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$project = Split-Path -Parent $PSScriptRoot
$sourcePath = Join-Path $project 'scripts\install_windows.ps1'
$tokens = $null; $parseErrors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($sourcePath, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw $parseErrors[0] }
$fixture = Join-Path ([IO.Path]::GetTempPath()) ('claude-zh-windows-test-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $fixture -Force | Out-Null
$fixtureScriptRoot = (Join-Path $fixture 'package\scripts').Replace("'", "''")
foreach ($definition in $ast.FindAll({ param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] }, $false)) {
    Invoke-Expression ($definition.Extent.Text.Replace('$PSScriptRoot', "'$fixtureScriptRoot'"))
}
$Utf8NoBom = [Text.UTF8Encoding]::new($false)
$OnlineTranslationMaxSourceLength = 1000
$script:CurrentBackupSetPath = $null
$checks = 0
function Assert([bool]$Passed, [string]$Message) {
    if (-not $Passed) { throw "FAIL: $Message" }
    $script:checks++
    Write-Host "PASS: $Message"
}
function Write-FixtureJson([string]$Path, [string]$Json) {
    New-Item -ItemType Directory -Path (Split-Path -Parent $Path) -Force | Out-Null
    [IO.File]::WriteAllText($Path, $Json, $Utf8NoBom)
}
try {
    $packDir = Join-Path $fixture 'package\resources'
    Write-FixtureJson (Join-Path $packDir 'frontend-zh-CN.json') '{"caseTitle":"标题扩展","caseUpper":"大写扩展","settings":"设置","low":"低","medium":"中","high":"高","extra":"极高","max":"最大","effort":"思考强度","stale":"过期译文"}'
    Write-FixtureJson (Join-Path $packDir 'desktop-zh-CN.json') '{"current":"当前桌面","stale":"过期桌面译文"}'
    Write-FixtureJson (Join-Path $packDir 'statsig-zh-CN.json') '{"flag":"开关"}'
    Write-FixtureJson (Join-Path $packDir 'dynamic-zh-CN.json') '{"current":"当前会话","domain":"域名操作","template":"{weekday} {time} 重置","stale":"过期动态译文"}'
    Write-FixtureJson (Join-Path $packDir 'frontend-hardcoded-zh-CN.json') '[["Effort","思考强度"],["LOW","大写低"]]'
    foreach ($name in @('frontend','desktop','statsig','frontend-hardcoded')) {
        Copy-Item -LiteralPath (Join-Path $packDir "$name-zh-CN.json") -Destination (Join-Path $packDir "$name-zh-TW.json")
    }
    $pack = Get-LanguageResources 'zh-CN'
    $traditionalPack = Get-LanguageResources 'zh-TW'
    Assert ($pack.ContainsKey('Dynamic')) 'optional dynamic catalog is discovered'
    Assert (-not $traditionalPack.ContainsKey('Dynamic')) 'language without a dynamic translation remains supported'

    $resources = Join-Path $fixture 'app\resources'
    Write-FixtureJson (Join-Path $resources 'ion-dist\i18n\en-US.json') '{"caseTitle":"Extensions","caseUpper":"EXTENSIONS","settings":"Settings","low":"Low","medium":"Medium","high":"High","extra":"Extra","max":"Max","effort":"Effort","fallback":"New frontend key"}'
    Write-FixtureJson (Join-Path $resources 'en-US.json') '{"current":"Current desktop","fallback":"New desktop key"}'
    Write-FixtureJson (Join-Path $resources 'ion-dist\i18n\dynamic\en-US.json') '{"current":"Current session","domain":"Domain actions","fallback":"New dynamic key","template":"Resets {weekday} {time}"}'
    $existingLocales = @('ion-dist\i18n\zh-CN.json','zh-CN.json','ion-dist\i18n\statsig\zh-CN.json','ion-dist\i18n\dynamic\zh-CN.json')
    foreach ($relative in $existingLocales) {
        Write-FixtureJson (Join-Path $resources $relative) '{"original":"Native locale"}'
    }
    Install-LanguageFiles $resources $pack 'zh-CN'
    $frontend = Get-Content -LiteralPath (Join-Path $resources 'ion-dist\i18n\zh-CN.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $desktop = Get-Content -LiteralPath (Join-Path $resources 'zh-CN.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $dynamic = Get-Content -LiteralPath (Join-Path $resources 'ion-dist\i18n\dynamic\zh-CN.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    Assert ($frontend.caseTitle -eq '标题扩展' -and $frontend.fallback -eq 'New frontend key' -and -not $frontend.PSObject.Properties['stale']) 'frontend baseline merge is preserved'
    Assert ($desktop.current -eq '当前桌面' -and $desktop.fallback -eq 'New desktop key' -and -not $desktop.PSObject.Properties['stale']) 'desktop baseline merge is preserved'
    Assert ($dynamic.current -eq '当前会话' -and $dynamic.fallback -eq 'New dynamic key' -and -not $dynamic.PSObject.Properties['stale']) 'dynamic catalog merges current keys and retains English fallback'
    Install-LanguageFiles $resources $pack 'zh-CN'
    Install-LanguageFiles $resources $traditionalPack 'zh-TW'
    Install-LanguageFiles $resources $traditionalPack 'zh-TW'
    $dynamicFallback = Get-Content -LiteralPath (Join-Path $resources 'ion-dist\i18n\dynamic\zh-TW.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    Assert ($dynamicFallback.current -eq 'Current session' -and $dynamicFallback.fallback -eq 'New dynamic key') 'missing dynamic translation copies the installed English catalog'
    $backup = $script:CurrentBackupSetPath
    $metadata = Get-JsonObjectOrBackup (Join-Path $backup '.backup-metadata.json')
    Assert (@($metadata.createdFiles).Count -eq 4) 'repeat install tracks four created locales only once'
    Assert (-not (Test-Path -LiteralPath (Join-Path $backup 'zh-TW.json'))) 'repeat install does not back up its own newly created locale'

    $mapping = Get-OnlineTranslationMap $resources $pack 'zh-CN'
    Assert ($mapping['Extensions'] -eq '标题扩展' -and $mapping['EXTENSIONS'] -eq '大写扩展') 'online map preserves case-distinct source strings'
    Assert ($mapping['Current session'] -eq '当前会话' -and $mapping['Domain actions'] -eq '域名操作') 'online map includes current dynamic catalog translations'
    Assert (-not $mapping.Contains('Resets {weekday} {time}')) 'unresolved ICU messages are excluded from DOM replacement'
    foreach ($label in @('Low','Medium','High','Extra','Max','Effort')) {
        Assert (-not $mapping.Contains($label)) "effort label stays English: $label"
    }
    Assert ($mapping['LOW'] -eq '大写低') 'effort exclusion uses exact case'
    $generated = Get-OnlineDomTranslationScript 'zh-CN' $mapping
    Assert (-not [regex]::IsMatch($generated, '__[A-Z][A-Z0-9_]*__')) 'real PowerShell generator resolves every placeholder'
    $generatedPath = Join-Path $fixture 'generated-dom.js'
    [IO.File]::WriteAllText($generatedPath, $generated, $Utf8NoBom)
    & node --check $generatedPath
    Assert ($LASTEXITCODE -eq 0) 'real PowerShell-generated JavaScript parses'
    $checkPath = Join-Path $fixture 'check-generated-dom.js'
    [IO.File]::WriteAllText($checkPath, 'const s=require("fs").readFileSync(process.argv[2],"utf8");globalThis.window=globalThis;globalThis.localStorage={setItem(){}};globalThis.document={documentElement:{setAttribute(){}},body:null};globalThis.MutationObserver=class{observe(){}};eval(s.replace("const X=","globalThis.testR=R;const X="));const a=require("assert/strict");a.equal(testR("Extensions"),"标题扩展");a.equal(testR("EXTENSIONS"),"大写扩展");a.equal(testR("Low"),undefined);a.equal(testR("Resets Sunday 12:00 AM"),"周日 00:00 重置");a.equal(testR("Resets in 2h 15m"),"2 小时 15 分钟后重置");a.equal(testR("Oct 3, 2026"),"2026年10月3日");', $Utf8NoBom)
    & node $checkPath $generatedPath
    Assert ($LASTEXITCODE -eq 0) 'real generated translator handles Unicode, callbacks, and multiple capture groups'
    $pairs = @(Get-ModelPickerReplacementPairs 'zh-CN')
    Assert ($pairs.Count -eq 4 -and @($pairs | Where-Object { $_[0] -match '^(name:|message:)' }).Count -eq 0) 'CN model picker translates four descriptions and preserves original labels'
    $installSource = ($ast.FindAll({ param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Install-WindowsLanguagePack' }, $false)[0]).Extent.Text
    Assert ($installSource.IndexOf('Patch-HardcodedMainProcessMenuLabels') -lt $installSource.IndexOf('Patch-ModelPickerStrings') -and $installSource.IndexOf('Patch-ModelPickerStrings') -lt $installSource.IndexOf('Patch-OnlineDomTranslation')) 'online patch is injected after menu and model replacements'

    Restore-LatestBackup $resources
    Remove-LanguageFiles $resources
    foreach ($relative in $existingLocales) {
        Assert ([IO.File]::ReadAllText((Join-Path $resources $relative)) -eq '{"original":"Native locale"}') "uninstall restores and preserves preexisting locale: $relative"
    }
    Assert (@(Get-LanguageFileTargets $resources | Where-Object { $_ -like '*zh-TW.json' -and (Test-Path -LiteralPath $_) }).Count -eq 0) 'uninstall removes all newly created locales including dynamic'
    Assert (-not (Test-Path -LiteralPath (Join-Path $resources '.backup-metadata.json'))) 'backup metadata is never restored into application resources'

    $legacyResources = Join-Path $fixture 'legacy\resources'
    $legacyBackup = Join-Path $legacyResources '.zh-cn-backups\20260101-000000'
    Write-FixtureJson (Join-Path $legacyBackup 'marker.json') '{}'
    Write-FixtureJson (Join-Path $legacyResources 'zh-CN.json') '{"oldPatch":true}'
    $script:CurrentBackupSetPath = $null
    Backup-LanguageFile $legacyResources (Join-Path $legacyResources 'zh-CN.json')
    $legacyMetadata = Get-JsonObjectOrBackup (Join-Path $legacyBackup '.backup-metadata.json')
    Assert (@($legacyMetadata.createdFiles) -contains 'zh-CN.json') 'legacy backups retain cleanup tracking for old unbacked locale files'
    Assert (-not (Test-Path -LiteralPath (Join-Path $legacyBackup 'zh-CN.json'))) 'legacy patched locale is not mistaken for an original backup'
    Write-Host "Windows localization checks passed: $checks"
}
finally {
    $resolved = [IO.Path]::GetFullPath($fixture)
    $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') + '\'
    if ($resolved.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase) -and (Split-Path -Leaf $resolved).StartsWith('claude-zh-windows-test-')) {
        Remove-Item -LiteralPath $resolved -Recurse -Force
    } else {
        throw "Refusing to remove a fixture outside the expected temporary directory: $resolved"
    }
}
