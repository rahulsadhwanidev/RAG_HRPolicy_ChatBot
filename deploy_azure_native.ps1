# Azure Native Deployment Script
# Deploys HR Policy Chatbot with 100% Azure services
# Requires: Azure OpenAI access approval

param(
    [string]$ResourceGroup = "rg-hr-chatbot",
    [string]$Location = "eastus",
    [switch]$SkipOpenAI = $false
)

Write-Host "================================================" -ForegroundColor Cyan
Write-Host " HR Policy Chatbot - Full Azure Stack Deployment" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Check Azure CLI
try {
    az --version | Out-Null
    Write-Host "[OK] Azure CLI installed" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Azure CLI not installed" -ForegroundColor Red
    exit 1
}

# Check login
$account = az account show 2>$null | ConvertFrom-Json
if (-not $account) {
    Write-Host "Logging in to Azure..." -ForegroundColor Yellow
    az login
}
Write-Host "[OK] Logged in as: $($account.user.name)" -ForegroundColor Green
Write-Host ""

# Configuration
Write-Host "Deployment Configuration:" -ForegroundColor Cyan
Write-Host "  Resource Group: $ResourceGroup" -ForegroundColor White
Write-Host "  Location: $Location" -ForegroundColor White
Write-Host ""

# Check Azure OpenAI access
if (-not $SkipOpenAI) {
    Write-Host "Checking Azure OpenAI access..." -ForegroundColor Yellow
    $openaiCheck = az provider show --namespace Microsoft.CognitiveServices --query "registrationState" -o tsv 2>$null
    if ($openaiCheck -ne "Registered") {
        Write-Host "[WARNING] Azure OpenAI may not be available" -ForegroundColor Yellow
        Write-Host "Apply for access at: https://aka.ms/oai/access" -ForegroundColor Yellow
        $continue = Read-Host "Continue anyway? (yes/no)"
        if ($continue -ne "yes") { exit 0 }
    }
}

Write-Host ""
$confirm = Read-Host "Proceed with deployment? (yes/no)"
if ($confirm -ne "yes") { exit 0 }

# ========================================
# Step 1: Create Resource Group
# ========================================
Write-Host ""
Write-Host "[1/8] Creating Resource Group..." -ForegroundColor Yellow
az group create --name $ResourceGroup --location $Location --output none
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Resource Group created" -ForegroundColor Green
} else {
    Write-Host "[ERROR] Failed" -ForegroundColor Red
    exit 1
}

# ========================================
# Step 2: Create Azure Storage
# ========================================
Write-Host ""
Write-Host "[2/8] Creating Azure Blob Storage..." -ForegroundColor Yellow
$StorageAccount = "hrchatbot$(Get-Random -Maximum 9999)"

az storage account create `
    --name $StorageAccount `
    --resource-group $ResourceGroup `
    --location $Location `
    --sku Standard_LRS `
    --kind StorageV2 `
    --output none

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to create storage" -ForegroundColor Red
    exit 1
}

$StorageKey = az storage account keys list `
    --resource-group $ResourceGroup `
    --account-name $StorageAccount `
    --query '[0].value' `
    --output tsv

$StorageConnection = az storage account show-connection-string `
    --name $StorageAccount `
    --resource-group $ResourceGroup `
    --output tsv

az storage container create --name "documents" --account-name $StorageAccount --account-key $StorageKey --output none
Write-Host "[OK] Storage Account created: $StorageAccount" -ForegroundColor Green

# ========================================
# Step 3: Create Azure OpenAI
# ========================================
if (-not $SkipOpenAI) {
    Write-Host ""
    Write-Host "[3/8] Creating Azure OpenAI Service..." -ForegroundColor Yellow
    $OpenAIName = "openai-hr-$(Get-Random -Maximum 9999)"

    az cognitiveservices account create `
        --name $OpenAIName `
        --resource-group $ResourceGroup `
        --location $Location `
        --kind OpenAI `
        --sku S0 `
        --custom-domain $OpenAIName `
        --output none

    if ($LASTEXITCODE -ne 0) {
        Write-Host "[WARNING] Could not create Azure OpenAI (may need approval)" -ForegroundColor Yellow
        Write-Host "You can manually create it later or use OpenAI API" -ForegroundColor Yellow
        $OpenAIEndpoint = ""
        $OpenAIKey = ""
    } else {
        Write-Host "  Deploying GPT-4o-mini model..." -ForegroundColor Yellow
        az cognitiveservices account deployment create `
            --name $OpenAIName `
            --resource-group $ResourceGroup `
            --deployment-name "gpt-4o-mini" `
            --model-name "gpt-4o-mini" `
            --model-version "2024-07-18" `
            --model-format OpenAI `
            --sku-capacity 10 `
            --sku-name "Standard" `
            --output none

        Write-Host "  Deploying text-embedding-3-small model..." -ForegroundColor Yellow
        az cognitiveservices account deployment create `
            --name $OpenAIName `
            --resource-group $ResourceGroup `
            --deployment-name "text-embedding-3-small" `
            --model-name "text-embedding-3-small" `
            --model-version "1" `
            --model-format OpenAI `
            --sku-capacity 10 `
            --sku-name "Standard" `
            --output none

        $OpenAIEndpoint = az cognitiveservices account show `
            --name $OpenAIName `
            --resource-group $ResourceGroup `
            --query "properties.endpoint" `
            --output tsv

        $OpenAIKey = az cognitiveservices account keys list `
            --name $OpenAIName `
            --resource-group $ResourceGroup `
            --query "key1" `
            --output tsv

        Write-Host "[OK] Azure OpenAI created: $OpenAIName" -ForegroundColor Green
    }
} else {
    Write-Host ""
    Write-Host "[3/8] Skipping Azure OpenAI (will use OpenAI API)" -ForegroundColor Yellow
    $OpenAIEndpoint = ""
    $OpenAIKey = ""
}

# ========================================
# Step 4: Create Azure AI Search
# ========================================
Write-Host ""
Write-Host "[4/8] Creating Azure AI Search..." -ForegroundColor Yellow
$SearchName = "search-hr-$(Get-Random -Maximum 9999)"

$useSearch = Read-Host "Deploy Azure AI Search? (~$75/month) or use ChromaDB ($0)? (search/chromadb)"

if ($useSearch -eq "search") {
    az search service create `
        --name $SearchName `
        --resource-group $ResourceGroup `
        --location $Location `
        --sku Basic `
        --partition-count 1 `
        --replica-count 1 `
        --output none

    if ($LASTEXITCODE -eq 0) {
        $SearchKey = az search admin-key show `
            --service-name $SearchName `
            --resource-group $ResourceGroup `
            --query "primaryKey" `
            --output tsv

        $SearchEndpoint = "https://$SearchName.search.windows.net"
        Write-Host "[OK] Azure AI Search created: $SearchName" -ForegroundColor Green
    } else {
        Write-Host "[WARNING] Azure AI Search creation failed, will use ChromaDB" -ForegroundColor Yellow
        $SearchEndpoint = ""
        $SearchKey = ""
    }
} else {
    Write-Host "[OK] Using ChromaDB (local vector database)" -ForegroundColor Green
    $SearchEndpoint = ""
    $SearchKey = ""
}

# ========================================
# Step 5: Create Azure Key Vault
# ========================================
Write-Host ""
Write-Host "[5/8] Creating Azure Key Vault..." -ForegroundColor Yellow
$KeyVaultName = "kv-hr-$(Get-Random -Maximum 9999)"

az keyvault create `
    --name $KeyVaultName `
    --resource-group $ResourceGroup `
    --location $Location `
    --output none

if ($LASTEXITCODE -eq 0) {
    # Store secrets
    if ($OpenAIKey) {
        az keyvault secret set --vault-name $KeyVaultName --name "AzureOpenAIKey" --value $OpenAIKey --output none
    }
    if ($SearchKey) {
        az keyvault secret set --vault-name $KeyVaultName --name "SearchKey" --value $SearchKey --output none
    }
    az keyvault secret set --vault-name $KeyVaultName --name "StorageConnection" --value $StorageConnection --output none

    Write-Host "[OK] Key Vault created: $KeyVaultName" -ForegroundColor Green
} else {
    Write-Host "[WARNING] Key Vault creation failed" -ForegroundColor Yellow
    $KeyVaultName = ""
}

# ========================================
# Step 6: Create App Service
# ========================================
Write-Host ""
Write-Host "[6/8] Creating Azure App Service..." -ForegroundColor Yellow
$AppName = "hr-chatbot-$(Get-Random -Maximum 9999)"
$PlanName = "asp-hr-chatbot"

az appservice plan create `
    --name $PlanName `
    --resource-group $ResourceGroup `
    --sku B1 `
    --is-linux `
    --output none

az webapp create `
    --name $AppName `
    --resource-group $ResourceGroup `
    --plan $PlanName `
    --runtime "PYTHON:3.11" `
    --output none

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to create App Service" -ForegroundColor Red
    exit 1
}

# Enable managed identity
az webapp identity assign --name $AppName --resource-group $ResourceGroup --output none

# Grant Key Vault access
if ($KeyVaultName) {
    $Identity = az webapp identity show `
        --name $AppName `
        --resource-group $ResourceGroup `
        --query "principalId" `
        --output tsv

    az keyvault set-policy `
        --name $KeyVaultName `
        --object-id $Identity `
        --secret-permissions get list `
        --output none
}

Write-Host "[OK] App Service created: $AppName" -ForegroundColor Green

# ========================================
# Step 7: Configure App Settings
# ========================================
Write-Host ""
Write-Host "[7/8] Configuring Application..." -ForegroundColor Yellow

# Ask for API keys if not using Azure OpenAI
if (-not $OpenAIKey) {
    Write-Host "Enter OpenAI API Key (or press Enter to skip):" -ForegroundColor Yellow
    $OpenAIAPIKey = Read-Host -AsSecureString
    $OpenAIAPIKeyPlain = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto([System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($OpenAIAPIKey))
} else {
    $OpenAIAPIKeyPlain = ""
}

# Build settings
$settings = @()
$settings += "AZURE_STORAGE_CONNECTION_STRING=$StorageConnection"
$settings += "AZURE_CONTAINER_NAME=documents"
$settings += "DOC_ID=doc-001"
$settings += "THRESHOLD=0.15"
$settings += "TOP_K=6"
$settings += "WEBSITES_PORT=8000"
$settings += "SCM_DO_BUILD_DURING_DEPLOYMENT=true"

if ($OpenAIEndpoint) {
    $settings += "AZURE_OPENAI_ENDPOINT=$OpenAIEndpoint"
    $settings += "AZURE_OPENAI_KEY=$OpenAIKey"
    $settings += "AZURE_OPENAI_DEPLOYMENT_CHAT=gpt-4o-mini"
    $settings += "AZURE_OPENAI_DEPLOYMENT_EMBED=text-embedding-3-small"
    $settings += "USE_AZURE_OPENAI=true"
} elseif ($OpenAIAPIKeyPlain) {
    $settings += "OPENAI_API_KEY=$OpenAIAPIKeyPlain"
    $settings += "CHAT_MODEL=gpt-4o-mini"
    $settings += "EMBEDDING_MODEL=text-embedding-3-small"
}

if ($SearchEndpoint) {
    $settings += "AZURE_SEARCH_ENDPOINT=$SearchEndpoint"
    $settings += "AZURE_SEARCH_KEY=$SearchKey"
    $settings += "AZURE_SEARCH_INDEX=hr-policy-chunks"
    $settings += "USE_AZURE_SEARCH=true"
}

if ($KeyVaultName) {
    $settings += "AZURE_KEYVAULT_URI=https://$KeyVaultName.vault.azure.net/"
}

az webapp config appsettings set `
    --name $AppName `
    --resource-group $ResourceGroup `
    --settings @settings `
    --output none

az webapp config set `
    --name $AppName `
    --resource-group $ResourceGroup `
    --startup-file "startup.sh" `
    --output none

az webapp update `
    --name $AppName `
    --resource-group $ResourceGroup `
    --https-only true `
    --output none

Write-Host "[OK] Application configured" -ForegroundColor Green

# ========================================
# Step 8: Deploy Application
# ========================================
Write-Host ""
Write-Host "[8/8] Deploying Application Code..." -ForegroundColor Yellow

$deployZip = "deploy_$(Get-Date -Format 'yyyyMMddHHmmss').zip"
Compress-Archive -Path app,web,requirements.txt,startup.sh,.deployment,runtime.txt -DestinationPath $deployZip -Force

az webapp deployment source config-zip `
    --name $AppName `
    --resource-group $ResourceGroup `
    --src $deployZip `
    --output none

Remove-Item $deployZip -Force

if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Application deployed" -ForegroundColor Green
} else {
    Write-Host "[WARNING] Deployment may have issues, check logs" -ForegroundColor Yellow
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
Write-Host "Azure Resources Created:" -ForegroundColor Yellow
Write-Host "  Resource Group: $ResourceGroup" -ForegroundColor White
Write-Host "  Storage Account: $StorageAccount" -ForegroundColor White
if ($OpenAIName) {
    Write-Host "  Azure OpenAI: $OpenAIName" -ForegroundColor White
}
if ($SearchName) {
    Write-Host "  Azure AI Search: $SearchName" -ForegroundColor White
}
if ($KeyVaultName) {
    Write-Host "  Key Vault: $KeyVaultName" -ForegroundColor White
}
Write-Host "  App Service: $AppName" -ForegroundColor White
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "  1. Upload PDF documents to storage container 'documents'" -ForegroundColor White
Write-Host "  2. Create manifest.json: {\"latest_pdf\": \"doc-001/your-file.pdf\"}" -ForegroundColor White
Write-Host "  3. Visit $AppName.azurewebsites.net/ui to test" -ForegroundColor White
Write-Host ""
Write-Host "View logs:" -ForegroundColor Yellow
Write-Host "  az webapp log tail --name $AppName --resource-group $ResourceGroup" -ForegroundColor White
Write-Host ""
Write-Host "Estimated monthly cost: $($SearchEndpoint ? '~$103' : '~$15-25')" -ForegroundColor Yellow
Write-Host ""