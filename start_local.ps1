# Script PowerShell pentru pornirea instantanee a Recepționerului AI 24/7 pe Windows
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  Pornire Receptioner & Call-Center AI 24/7 (Cost 0 EUR)" -ForegroundColor Cyan
Write-Host "  URL Local: http://localhost:7860" -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Cyan

Set-Location -Path $PSScriptRoot

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "[INFO] Am creat fisierul .env din .env.example." -ForegroundColor Yellow
}

uv run --with-requirements requirements.txt uvicorn app.main:app --host 0.0.0.0 --port 7860
