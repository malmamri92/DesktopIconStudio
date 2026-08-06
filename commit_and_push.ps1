# commit_and_push.ps1
# يرفع أي تعديلات محلية إلى GitHub.
# الاستخدام: .\commit_and_push.ps1 "وصف التعديل"
param(
    [Parameter(Mandatory=$true)]
    [string]$Message
)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $repo

git add .
git commit -m "$Message" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
git push origin main

Write-Host "✅ تم رفع التعديلات إلى GitHub." -ForegroundColor Green
