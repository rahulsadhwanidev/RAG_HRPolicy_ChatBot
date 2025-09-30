# Azure Deployment Script
# PowerShell script to deploy HR Policy Chatbot to Azure

param(
    [string]$ResourceGroup = "rg-hr-chatbot",
    [string]$Location = "eastus",
    [string]$StorageAccount = "",
    [string]$AppServicePlan = "asp-hr-chatbot",
    [string]$WebAppName = ""
)

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "HR Policy Chatbot - Azure Deployment" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Check if Azure CLI is installed
try {
    az --version | Out-Null
    Write-Host "[OK] Azure CLI is installed" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Azure CLI is not installed" -ForegroundColor Red
    Write-Host "Install from: https://aka.ms/installazurecliwindows" -ForegroundColor Yellow
    exit 1
}

# Login to Azure
Write-Host ""
Write-Host "Checking Azure login..." -ForegroundColor Yellow
$account = az account show 2>$null | ConvertFrom-Json
if (-not $account) {
    Write-Host "Please login to Azure..." -ForegroundColor Yellow
    az login
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Azure login failed" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "[OK] Logged in as: $($account.user.name)" -ForegroundColor Green
}

# Generate unique names if not provided
if (-not $StorageAccount) {
    $random = Get-Random -Maximum 9999
    $StorageAccount = "hrchatbot$random"
}
if (-not $WebAppName) {
    $random = Get-Random -Maximum 9999
    $WebAppName = "hr-chatbot-$random"
}

Write-Host ""
Write-Host "Deployment Configuration:" -ForegroundColor Cyan
Write-Host "  Resource Group:    $ResourceGroup" -ForegroundColor White
Write-Host "  Location:          $Location" -ForegroundColor White
Write-Host "  Storage Account:   $StorageAccount" -ForegroundColor White
Write-Host "  App Service Plan:  $AppServicePlan" -ForegroundColor White
Write-Host "  Web App Name:      $WebAppName" -ForegroundColor White
Write-Host ""

# Ask for confirmation
$confirm = Read-Host "Proceed with deployment? (yes/no)"
if ($confirm -ne "yes") {
    Write-Host "Deployment cancelled" -ForegroundColor Yellow
    exit 0
}

# Step 1: Create Resource Group
Write-Host ""
Write-Host "[1/6] Creating Resource Group..." -ForegroundColor Yellow
az group create --name $ResourceGroup --location $Location --output none
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Resource Group created" -ForegroundColor Green
} else {
    Write-Host "[ERROR] Failed to create Resource Group" -ForegroundColor Red
    exit 1
}

# Step 2: Create Storage Account
Write-Host ""
Write-Host "[2/6] Creating Storage Account..." -ForegroundColor Yellow
az storage account create `
    --name $StorageAccount `
    --resource-group $ResourceGroup `
    --location $Location `
    --sku Standard_LRS `
    --kind StorageV2 `
    --output none

if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Storage Account created" -ForegroundColor Green
} else {
    Write-Host "[ERROR] Failed to create Storage Account" -ForegroundColor Red
    exit 1
}

# Get Storage Account Key
$StorageKey = az storage account keys list `
    --resource-group $ResourceGroup `
    --account-name $StorageAccount `
    --query '[0].value' `
    --output tsv

# Create containers
Write-Host "  Creating blob containers..." -ForegroundColor Yellow
az storage container create --name "documents" --account-name $StorageAccount --account-key $StorageKey --output none
az storage container create --name "chromadb" --account-name $StorageAccount --account-key $StorageKey --output none
Write-Host "[OK] Containers created" -ForegroundColor Green

# Step 3: Create App Service Plan
Write-Host ""
Write-Host "[3/6] Creating App Service Plan..." -ForegroundColor Yellow
az appservice plan create `
    --name $AppServicePlan `
    --resource-group $ResourceGroup `
    --sku B1 `
    --is-linux `
    --output none

if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] App Service Plan created" -ForegroundColor Green
} else {
    Write-Host "[ERROR] Failed to create App Service Plan" -ForegroundColor Red
    exit 1
}

# Step 4: Create Web App
Write-Host ""
Write-Host "[4/6] Creating Web App..." -ForegroundColor Yellow
az webapp create `
    --name $WebAppName `
    --resource-group $ResourceGroup `
    --plan $AppServicePlan `
    --runtime "PYTHON:3.11" `
    --output none

if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Web App created" -ForegroundColor Green
} else {
    Write-Host "[ERROR] Failed to create Web App" -ForegroundColor Red
    exit 1
}

# Step 5: Configure App Settings
Write-Host ""
Write-Host "[5/6] Configuring App Settings..." -ForegroundColor Yellow

# Prompt for OpenAI API Key
$OpenAIKey = Read-Host "Enter your OpenAI API Key" -AsSecureString
$OpenAIKeyPlain = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto([System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($OpenAIKey))

# Get connection string
$ConnectionString = az storage account show-connection-string `
    --name $StorageAccount `
    --resource-group $ResourceGroup `
    --output tsv

az webapp config appsettings set `
    --name $WebAppName `
    --resource-group $ResourceGroup `
    --settings `
        OPENAI_API_KEY="$OpenAIKeyPlain" `
        CHAT_MODEL="gpt-4o-mini" `
        EMBEDDING_MODEL="text-embedding-3-small" `
        AZURE_STORAGE_CONNECTION_STRING="$ConnectionString" `
        AZURE_CONTAINER_NAME="documents" `
        AZURE_CHROMADB_CONTAINER="chromadb" `
        DOC_ID="doc-001" `
        THRESHOLD="0.15" `
        TOP_K="6" `
        SCM_DO_BUILD_DURING_DEPLOYMENT="true" `
        WEBSITES_PORT="8000" `
    --output none

if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] App Settings configured" -ForegroundColor Green
} else {
    Write-Host "[ERROR] Failed to configure App Settings" -ForegroundColor Red
    exit 1
}

# Configure startup command
az webapp config set `
    --name $WebAppName `
    --resource-group $ResourceGroup `
    --startup-file "startup.sh" `
    --output none

# Enable HTTPS only
az webapp update `
    --name $WebAppName `
    --resource-group $ResourceGroup `
    --https-only true `
    --output none

# Step 6: Deploy Code
Write-Host ""
Write-Host "[6/6] Deploying Application..." -ForegroundColor Yellow
Write-Host "  This may take several minutes..." -ForegroundColor Yellow

# Create deployment package
$timestamp = Get-Date -Format "yyyyMMddHHmmss"
$zipFile = "deploy_$timestamp.zip"

# Files to include
$files = @(
    "app",
    "web",
    "requirements.txt",
    "startup.sh",
    ".deployment",
    "runtime.txt"
)

Write-Host "  Creating deployment package..." -ForegroundColor Yellow
Compress-Archive -Path $files -DestinationPath $zipFile -Force

# Deploy via ZIP
az webapp deployment source config-zip `
    --name $WebAppName `
    --resource-group $ResourceGroup `
    --src $zipFile `
    --output none

if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Application deployed" -ForegroundColor Green
    Remove-Item $zipFile -Force
} else {
    Write-Host "[ERROR] Deployment failed" -ForegroundColor Red
    Remove-Item $zipFile -Force
    exit 1
}

# Summary
Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Application URL:" -ForegroundColor Yellow
Write-Host "  https://$WebAppName.azurewebsites.net" -ForegroundColor White
Write-Host ""
Write-Host "Web UI:" -ForegroundColor Yellow
Write-Host "  https://$WebAppName.azurewebsites.net/ui" -ForegroundColor White
Write-Host ""
Write-Host "API Documentation:" -ForegroundColor Yellow
Write-Host "  https://$WebAppName.azurewebsites.net/docs" -ForegroundColor White
Write-Host ""
Write-Host "Storage Account:" -ForegroundColor Yellow
Write-Host "  $StorageAccount" -ForegroundColor White
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "  1. Upload your PDF documents to the 'documents' container" -ForegroundColor White
Write-Host "  2. Create manifest.json with document references" -ForegroundColor White
Write-Host "  3. Visit the app URL to test the chatbot" -ForegroundColor White
Write-Host ""
Write-Host "To view logs:" -ForegroundColor Yellow
Write-Host "  az webapp log tail --name $WebAppName --resource-group $ResourceGroup" -ForegroundColor White
Write-Host ""