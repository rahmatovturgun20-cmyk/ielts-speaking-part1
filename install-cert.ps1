$ErrorActionPreference = 'Stop'
$log = "C:\Users\ACER\Desktop\Speaking part 1\cert-import-result.txt"
try {
    $cert = Import-Certificate -FilePath "C:\Users\ACER\Desktop\Speaking part 1\cert.pem" -CertStoreLocation Cert:\LocalMachine\Root
    "OK thumbprint=$($cert.Thumbprint)" | Out-File $log -Encoding utf8
} catch {
    "FAIL $_" | Out-File $log -Encoding utf8
}
Start-Sleep -Seconds 1
