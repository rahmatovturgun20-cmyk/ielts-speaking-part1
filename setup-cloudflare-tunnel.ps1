# Multilevel Mock Test - Cloudflare named tunnel sozlash (1 marta)
# Bu skriptni faqat Cloudflare akkauntga domain qo'shilgandan keyin ishga tushiring!

$ErrorActionPreference = "Stop"
$proj   = "C:\Users\ACER\Desktop\Speaking part 1"
$cf     = Join-Path $proj "cloudflared.exe"
$homeCf = Join-Path $env:USERPROFILE ".cloudflared"

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Cloudflare TUNNEL sozlash (multilevelmocktest.uz)" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

# --- Q1: Login ---
Write-Host ""
Write-Host "[1/5] Cloudflare login - brauzer ochiladi, akkauntingizga kiring" -ForegroundColor Yellow
& $cf tunnel login
if ($LASTEXITCODE -ne 0) {
    Write-Host "LOGIN muvaffaqiyatsiz bo'ldi. Qayta urinib ko'ring." -ForegroundColor Red
    exit 1
}
Write-Host "Login OK." -ForegroundColor Green

# --- Q2: Tunnel yaratish ---
Write-Host ""
Write-Host "[2/5] 'mocktest' tunnel yaratish..." -ForegroundColor Yellow
& $cf tunnel create mocktest
if ($LASTEXITCODE -ne 0) {
    Write-Host "(tunnel allaqachon mavjud bo'lishi mumkin - davom etamiz)" -ForegroundColor Yellow
}

# --- Q3: DNS yozuvlari ---
Write-Host ""
Write-Host "[3/5] DNS CNAME yozuvlari yaratish..." -ForegroundColor Yellow
Write-Host "  multilevelmocktest.uz  -> tunnel" -ForegroundColor Gray
& $cf tunnel route dns mocktest multilevelmocktest.uz
if ($LASTEXITCODE -ne 0) {
    Write-Host "!" -ForegroundColor Red -NoNewline
    Write-Host " Domain Cloudflare zonasi topilmadi. Avval domainni Cloudflare akkauntingizga qo'shing!"
}
Write-Host "  www.multilevelmocktest.uz  -> tunnel" -ForegroundColor Gray
& $cf tunnel route dns mocktest www.multilevelmocktest.uz
if ($LASTEXITCODE -ne 0) {
    Write-Host "!" -ForegroundColor Red -NoNewline
    Write-Host " www yozuvi yaratilmadi."
}

# --- Q4: config.yml ---
$cred = Get-ChildItem (Join-Path $homeCf "*.json") -ErrorAction SilentlyContinue |
    Where-Object { $_.BaseName -match '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' } |
    Select-Object -First 1
if (-not $cred) {
    Write-Host "Credential fayli topilmadi: ~/.cloudflared/*.json" -ForegroundColor Red
    exit 1
}
$config = @"
tunnel: mocktest
credentials-file: $($cred.FullName.Replace('\','/'))

ingress:
  - hostname: multilevelmocktest.uz
    service: http://localhost:8000
  - hostname: www.multilevelmocktest.uz
    service: http://localhost:8000
  - service: http_status:404
"@
Set-Content -LiteralPath (Join-Path $homeCf "config.yml") -Value $config -Encoding Ascii
Write-Host ""
Write-Host "[4/5] config.yml yozildi: $homeCf\config.yml" -ForegroundColor Green

# --- Avto-start fayllari ---
$startupDir  = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"
$navBat      = Join-Path $proj "start-named-tunnel.bat"
$startupVbs  = Join-Path $startupDir "start-cloudflared-hidden.vbs"
$vbsLine = 'CreateObject("WScript.Shell").Run "' + $navBat + '", 0, False'
$vbsBody = $vbsLine + "`r`n"
Set-Content -LiteralPath $startupVbs -Value $vbsBody -Encoding Ascii
Write-Host "[5/5] Avto-start yangilandi (start-named-tunnel.bat -> ishga tushganda avtomatik)" -ForegroundColor Green

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Test: tunnelleni 15 soniya ishga tushirish..." -ForegroundColor Yellow
Write-Host "================================================" -ForegroundColor Cyan

$p = Start-Process -FilePath $cf -ArgumentList @("tunnel","--config",(Join-Path $homeCf "config.yml"),"run","mocktest") -NoNewWindow -PassThru
Start-Sleep -Seconds 15

try {
    $r = Invoke-WebRequest -Uri "https://multilevelmocktest.uz/api/config-public" -TimeoutSec 15 -UseBasicParsing
    Write-Host ""
    Write-Host "SAYT ISHLADI! HTTP $($r.StatusCode)" -ForegroundColor Green
    Write-Host "https://multilevelmocktest.uz" -ForegroundColor Green
} catch {
    Write-Host ""
    Write-Host "Sayt hali javob bermadi. Sabablar:" -ForegroundColor Red
    Write-Host "  - DNS hali Cloudflare nameserver'lariga o'tmagan (bir necha soat kutish kerak)" -ForegroundColor Yellow
    Write-Host "  - Tunneldagi xatolik: tepadagi chiqishlarni tekshiring" -ForegroundColor Yellow
}

Stop-Process -Name cloudflared -Force -ErrorAction SilentlyContinue
Write-Host ""
Write-Host "================================================" -ForegroundColor Green
Write-Host " SOZLASH TUGADI!" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green
Write-Host ""
Write-Host "QOLGAN QADAMLAR:" -ForegroundColor Cyan
Write-Host "  1. Nameserver (NS) hali o'zgartirilmagan bo'lsa, domain regestrator paneldan" -ForegroundColor Yellow
Write-Host "     Cloudflare ko'rsatgan ikkita NS'ga almashtiring (Cloudflare dashboardda ko'rinadi)." -ForegroundColor Yellow
Write-Host "  2. NS o'tishi 10 daqiqadan 24 soatgacha davom etadi." -ForegroundColor Yellow
Write-Host "  3. Kamputer TAYLAK OLING va QAYTA YOQING - shundan keyin Flask + tunnel avtomatik ishlaydi" -ForegroundColor Green
Write-Host "     va sayt doimiy manzilda turadi: https://multilevelmocktest.uz" -ForegroundColor Green
Write-Host ""
Read-Host "Chiqish uchun Enter bosing..."