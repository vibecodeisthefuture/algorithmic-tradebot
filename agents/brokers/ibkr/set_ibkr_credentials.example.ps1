# ===================================
# IBKR Credentials Setup Script (TEMPLATE)
# ===================================
# This script sets environment variables for IBKR API authentication
#
# INSTRUCTIONS:
# 1. Copy this file to set_ibkr_credentials.ps1
# 2. Replace placeholders with your actual IBKR credentials
# 3. NEVER commit the actual credentials file to version control!
#
# cp set_ibkr_credentials.example.ps1 set_ibkr_credentials.ps1
# ===================================

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "IBKR Credentials Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Replace these with your actual IBKR credentials
$username = "YOUR_IBKR_USERNAME"
$password = "YOUR_IBKR_PASSWORD"

Write-Host "Setting environment variables..." -ForegroundColor Yellow
Write-Host ""

try {
    # Set for current session
    $env:IBKR_USERNAME = $username
    $env:IBKR_PASSWORD = $password

    Write-Host "[OK] Session variables set" -ForegroundColor Green

    # Set permanently for user
    [System.Environment]::SetEnvironmentVariable('IBKR_USERNAME', $username, 'User')
    [System.Environment]::SetEnvironmentVariable('IBKR_PASSWORD', $password, 'User')

    Write-Host "[OK] User environment variables set" -ForegroundColor Green
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "Setup Complete!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "NOTE: Restart PowerShell for permanent variables to take effect." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "To verify, run: " -ForegroundColor Cyan
    Write-Host '  $env:IBKR_USERNAME' -ForegroundColor White
    Write-Host ""

}
catch {
    Write-Host "[ERROR] Failed to set environment variables:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
