# Simple Azure Deployment Script
# No Key Vault, No complex permissions needed
# Works with basic Azure access

param(
    [string]$ResourceGroup = "rg-hr-chatbot",
    [string]$Location = "eastus"
)

Write-Host "================================================" -ForegroundColor Cyan
Write-Host " HR Chatbot - Simple Azure Deployment" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Check Azure CLI
$account = az account show 2>$null | ConvertFrom-Json
if (-not $account) {
    Write-Host "[ERROR] Not logged in to Azure" -ForegroundColor Red
    Write-Host "You should already be logged in via Cloud Shell" -ForegroundColor Yellow
    exit 1
}

Write-Host "[OK] Logged in as: $($account.user.name)" -ForegroundColor Green
Write-Host ""

# Configuration
Write-Host "Deployment Configuration:" -ForegroundColor Cyan
Write-Host "  Resource Group: $ResourceGroup" -ForegroundColor White
Write-Host "  Location: $Location" -ForegroundColor White
Write-Host ""

$confirm = Read-Host "Proceed with deployment? (yes/no)"
if ($confirm -ne "yes") { exit 0 }

# Generate unique names
$StorageAccount = "hrchatbot$(Get-Random -Maximum 9999)"
$AppName = "hr-chatbot-$(Get-Random -Maximum 9999)"
$PlanName = "asp-hr-chatbot"

# ========================================
# Step 1: Create or Use Existing Resource Group
# ========================================
Write-Host ""
Write-Host "[1/5] Checking Resource Group..." -ForegroundColor Yellow
$rgExists = az group exists --name $ResourceGroup

if ($rgExists -eq "true") {
    Write-Host "[OK] Resource Group already exists" -ForegroundColor Green
} else {
    Write-Host "Creating Resource Group..." -ForegroundColor Yellow
    az group create --name $ResourceGroup --location $Location --output none
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Resource Group created" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] Failed to create Resource Group" -ForegroundColor Red
        exit 1
    }
}

# ========================================
# Step 2: Create Storage Account
# ========================================
Write-Host ""
Write-Host "[2/5] Creating Azure Blob Storage..." -ForegroundColor Yellow

# Check if storage already exists
$existingStorage = az storage account list --resource-group $ResourceGroup --query "[?starts_with(name, 'hrchatbot')].name" -o tsv

if ($existingStorage) {
    $StorageAccount = $existingStorage
    Write-Host "[OK] Using existing Storage Account: $StorageAccount" -ForegroundColor Green
} else {
    az storage account create `
        --name $StorageAccount `
        --resource-group $ResourceGroup `
        --location $Location `
        --sku Standard_LRS `
        --kind StorageV2 `
        --output none

    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Failed to create Storage Account" -ForegroundColor Red
        exit 1
    }

    $StorageKey = az storage account keys list `
        --resource-group $ResourceGroup `
        --account-name $StorageAccount `
        --query '[0].value' `
        --output tsv

    # Create container
    az storage container create `
        --name "documents" `
        --account-name $StorageAccount `
        --account-key $StorageKey `
        --output none

    Write-Host "[OK] Storage Account created: $StorageAccount" -ForegroundColor Green
}

# Get connection string
$StorageConnection = az storage account show-connection-string `
    --name $StorageAccount `
    --resource-group $ResourceGroup `
    --output tsv

# ========================================
# Step 3: Create App Service Plan
# ========================================
Write-Host ""
Write-Host "[3/5] Creating App Service Plan..." -ForegroundColor Yellow

$planExists = az appservice plan show --name $PlanName --resource-group $ResourceGroup 2>$null

if ($planExists) {
    Write-Host "[OK] App Service Plan already exists" -ForegroundColor Green
} else {
    az appservice plan create `
        --name $PlanName `
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
}

# ========================================
# Step 4: Create Web App
# ========================================
Write-Host ""
Write-Host "[4/5] Creating Web App..." -ForegroundColor Yellow

# Check if app already exists
$existingApp = az webapp list --resource-group $ResourceGroup --query "[?starts_with(name, 'hr-chatbot')].name" -o tsv

if ($existingApp) {
    $AppName = $existingApp
    Write-Host "[OK] Using existing Web App: $AppName" -ForegroundColor Green
} else {
    az webapp create `
        --name $AppName `
        --resource-group $ResourceGroup `
        --plan $PlanName `
        --runtime "PYTHON:3.11" `
        --output none

    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Failed to create Web App" -ForegroundColor Red
        exit 1
    }
    Write-Host "[OK] Web App created: $AppName" -ForegroundColor Green
}

# ========================================
# Step 5: Configure and Deploy
# ========================================
Write-Host ""
Write-Host "[5/5] Configuring and Deploying Application..." -ForegroundColor Yellow

# Ask for OpenAI API key
Write-Host ""
Write-Host "Do you have an OpenAI API key?" -ForegroundColor Yellow
Write-Host "Get one from: https://platform.openai.com/api-keys" -ForegroundColor Cyan
$OpenAIKey = Read-Host "Enter your OpenAI API Key (or press Enter to configure later)"

if (-not $OpenAIKey) {
    Write-Host "[WARNING] No OpenAI key provided. You'll need to add it later." -ForegroundColor Yellow
    $OpenAIKey = "REPLACE_WITH_YOUR_KEY"
}

# Configure app settings
Write-Host "Configuring application settings..." -ForegroundColor Yellow

az webapp config appsettings set `
    --name $AppName `
    --resource-group $ResourceGroup `
    --settings `
        OPENAI_API_KEY="$OpenAIKey" `
        CHAT_MODEL="gpt-4o-mini" `
        EMBEDDING_MODEL="text-embedding-3-small" `
        AZURE_STORAGE_CONNECTION_STRING="$StorageConnection" `
        AZURE_CONTAINER_NAME="documents" `
        DOC_ID="doc-001" `
        THRESHOLD="0.15" `
        TOP_K="6" `
        WEBSITES_PORT="8000" `
        SCM_DO_BUILD_DURING_DEPLOYMENT="true" `
    --output none

# Set startup command
az webapp config set `
    --name $AppName `
    --resource-group $ResourceGroup `
    --startup-file "startup.sh" `
    --output none

# Enable HTTPS
az webapp update `
    --name $AppName `
    --resource-group $ResourceGroup `
    --https-only true `
    --output none

# Deploy code
Write-Host "Deploying application code..." -ForegroundColor Yellow
$deployZip = "deploy_$(Get-Date -Format 'yyyyMMddHHmmss').zip"

# Check if we're in the right directory
if (-not (Test-Path "app")) {
    Write-Host "[ERROR] Not in project directory. Run this from RAG_HRPolicy_ChatBot folder" -ForegroundColor Red
    exit 1
}

Compress-Archive -Path app,web,requirements.txt,startup.sh,.deployment,runtime.txt -DestinationPath $deployZip -Force -ErrorAction SilentlyContinue

if (Test-Path $deployZip) {
    az webapp deployment source config-zip `
        --name $AppName `
        --resource-group $ResourceGroup `
        --src $deployZip `
        --output none

    Remove-Item $deployZip -Force
    Write-Host "[OK] Application deployed" -ForegroundColor Green
} else {
    Write-Host "[ERROR] Failed to create deployment package" -ForegroundColor Red
}

# ========================================
# Summary
# ========================================
Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host " Deployment Complete!" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Application URL:" -ForegroundColor Yellow
Write-Host "  https://$AppName.azurewebsites.net" -ForegroundColor White
Write-Host ""
Write-Host "Web UI:" -ForegroundColor Yellow
Write-Host "  https://$AppName.azurewebsites.net/ui" -ForegroundColor White
Write-Host ""
Write-Host "API Docs:" -ForegroundColor Yellow
Write-Host "  https://$AppName.azurewebsites.net/docs" -ForegroundColor White
Write-Host ""
Write-Host "Azure Resources:" -ForegroundColor Yellow
Write-Host "  Resource Group: $ResourceGroup" -ForegroundColor White
Write-Host "  Storage Account: $StorageAccount" -ForegroundColor White
Write-Host "  App Service: $AppName" -ForegroundColor White
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "  1. Upload PDF documents to storage container 'documents'" -ForegroundColor White
Write-Host "  2. Create manifest.json: {\"latest_pdf\": \"doc-001/your-file.pdf\"}" -ForegroundColor White
Write-Host "  3. Visit the app URL to test" -ForegroundColor White
Write-Host ""
Write-Host "Upload documents in Azure Portal:" -ForegroundColor Yellow
Write-Host "  Portal -> Storage Accounts -> $StorageAccount -> Containers -> documents" -ForegroundColor White
Write-Host ""
Write-Host "View logs:" -ForegroundColor Yellow
Write-Host "  az webapp log tail --name $AppName --resource-group $ResourceGroup" -ForegroundColor White
Write-Host ""
Write-Host "Estimated monthly cost: ~`$15-25" -ForegroundColor Yellow
Write-Host ""

# Save deployment info
$deployInfo = @{
    timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    resourceGroup = $ResourceGroup
    storageAccount = $StorageAccount
    appName = $AppName
    appUrl = "https://$AppName.azurewebsites.net"
} | ConvertTo-Json

$deployInfo | Out-File "deployment-info.json" -Encoding utf8
Write-Host "Deployment info saved to: deployment-info.json" -ForegroundColor Cyan