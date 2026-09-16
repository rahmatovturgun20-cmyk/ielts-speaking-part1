$log = Join-Path $PSScriptRoot "cf.log"
$url = Select-String -LiteralPath $log -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' |
    Select-Object -Last 1 |
    ForEach-Object { [regex]::Match($_.Line, 'https://[a-z0-9-]+\.trycloudflare\.com').Value }
if ($url) {
    Set-Content -LiteralPath (Join-Path $PSScriptRoot "link.txt") -Value $url -Encoding Ascii
}