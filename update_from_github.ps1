# update_from_github.ps1
# يسحب آخر تحديثات الكود من GitHub، يعيد بناء ملف EXE،
# ويحدّث الاختصار على سطح المكتب.
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $repo

Write-Host "🔽 جارٍ سحب آخر التحديثات من GitHub..." -ForegroundColor Cyan
git pull origin main

Write-Host "📦 جارٍ تحديث المكتبات..." -ForegroundColor Cyan
pip install -r requirements.txt

Write-Host "🔧 جارٍ بناء ملف EXE..." -ForegroundColor Cyan
pyinstaller --noconsole --onefile --icon icon.ico --name "DesktopIconStudio" desktop_icon_studio.py

$exe = Join-Path $repo "dist\DesktopIconStudio.exe"
if (-not (Test-Path $exe)) {
    Write-Error "❌ فشل إنشاء ملف EXE."
    exit 1
}

Write-Host "🖥️ جارٍ تحديث اختصار سطح المكتب..." -ForegroundColor Cyan
$shortcutPath = "C:\Users\$env:USERNAME\Desktop\استوديو أيقونات سطح المكتب.lnk"
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($shortcutPath)
$Shortcut.TargetPath = $exe
$Shortcut.WorkingDirectory = $repo
$Shortcut.IconLocation = "$exe,0"
$Shortcut.Description = "Desktop Icon Studio v2"
$Shortcut.Save()

Write-Host "✅ تم التحديث بنجاح!" -ForegroundColor Green
Write-Host "   الكود: $repo" -ForegroundColor Gray
Write-Host "   EXE:   $exe" -ForegroundColor Gray
Write-Host "   اختصار سطح المكتب: $shortcutPath" -ForegroundColor Gray
