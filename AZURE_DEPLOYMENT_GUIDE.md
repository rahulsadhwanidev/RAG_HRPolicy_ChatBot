# Azure Deployment Guide - RAG HR Policy Chatbot

Complete guide to migrate from AWS and deploy to Azure for public access.

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Step 1: Migrate from AWS S3 to Azure Blob Storage](#step-1-migrate-from-aws-s3-to-azure-blob-storage)
4. [Step 2: Update Application Code](#step-2-update-application-code)
5. [Step 3: Deploy to Azure App Service](#step-3-deploy-to-azure-app-service)
6. [Step 4: Configure Domain and SSL](#step-4-configure-domain-and-ssl)
7. [Step 5: Monitoring and Scaling](#step-5-monitoring-and-scaling)
8. [Cost Estimation](#cost-estimation)
9. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

### Current Architecture (AWS)
```
AWS S3 (Documents) → FastAPI → ChromaDB (Local) → OpenAI API
```

### Target Architecture (Azure)
```
Azure Blob Storage (Documents) → Azure App Service (FastAPI) →
Azure Database for PostgreSQL (Optional) → OpenAI API
```

**Key Changes:**
- AWS S3 → **Azure Blob Storage**
- Local ChromaDB → **Azure Blob Storage** (persistent storage)
- Local hosting → **Azure App Service** (Web App)
- No DNS → **Custom Domain + SSL**

---

## Prerequisites

### 1. Azure Account
- Create account at: https://azure.microsoft.com/free/
- Free tier includes:
  - $200 credit for 30 days
  - 12 months of free services
  - Always free services

### 2. Azure CLI Installation
```bash
# Windows (PowerShell as Admin)
winget install Microsoft.AzureCLI

# Or download from: https://aka.ms/installazurecliwindows

# Verify installation
az --version
```

### 3. Required Azure Services
- **Azure Storage Account** (for documents + ChromaDB persistence)
- **Azure App Service** (for hosting FastAPI)
- **Azure Key Vault** (for secrets management)
- **Azure Application Insights** (optional monitoring)

---

## Step 1: Migrate from AWS S3 to Azure Blob Storage

### 1.1 Create Azure Storage Account

```bash
# Login to Azure
az login

# Set variables
$RESOURCE_GROUP="rg-hr-chatbot"
$LOCATION="eastus"
$STORAGE_ACCOUNT="hrchatbotstorage$(Get-Random -Maximum 9999)"
$CONTAINER_NAME="documents"

# Create resource group
az group create --name $RESOURCE_GROUP --location $LOCATION

# Create storage account
az storage account create `
  --name $STORAGE_ACCOUNT `
  --resource-group $RESOURCE_GROUP `
  --location $LOCATION `
  --sku Standard_LRS `
  --kind StorageV2

# Get storage account key
$STORAGE_KEY=$(az storage account keys list `
  --resource-group $RESOURCE_GROUP `
  --account-name $STORAGE_ACCOUNT `
  --query '[0].value' `
  --output tsv)

# Create blob container
az storage container create `
  --name $CONTAINER_NAME `
  --account-name $STORAGE_ACCOUNT `
  --account-key $STORAGE_KEY
```

### 1.2 Upload Documents to Azure Blob Storage

**Option A: Using Azure Portal**
1. Go to Azure Portal → Storage Accounts
2. Select your storage account
3. Click "Containers" → Select "documents"
4. Click "Upload"
5. Upload your PDF files

**Option B: Using Azure CLI**
```bash
# Upload PDF document
az storage blob upload `
  --account-name $STORAGE_ACCOUNT `
  --account-key $STORAGE_KEY `
  --container-name $CONTAINER_NAME `
  --name "doc-001/1234567890.pdf" `
  --file "path/to/your/document.pdf"

# Upload manifest.json
$manifestContent = @"
{
  "latest_pdf": "doc-001/1234567890.pdf"
}
"@

$manifestContent | Out-File -FilePath "manifest.json" -Encoding utf8
az storage blob upload `
  --account-name $STORAGE_ACCOUNT `
  --account-key $STORAGE_KEY `
  --container-name $CONTAINER_NAME `
  --name "doc-001/manifest.json" `
  --file "manifest.json"
```

**Option C: Using Azure Storage Explorer**
1. Download: https://azure.microsoft.com/features/storage-explorer/
2. Connect to your Azure account
3. Navigate to your storage account
4. Drag and drop files

### 1.3 Create ChromaDB Persistence Container

```bash
# Create container for ChromaDB data
az storage container create `
  --name "chromadb" `
  --account-name $STORAGE_ACCOUNT `
  --account-key $STORAGE_KEY
```

---

## Step 2: Update Application Code

### 2.1 Update requirements.txt

Add Azure dependencies:
```txt
fastapi
uvicorn[standard]
pydantic==2.8.2
python-multipart
pypdf
tiktoken
openai==1.40.1
chromadb==0.5.5
numpy
python-dotenv
httpx<0.28

# Azure dependencies
azure-storage-blob>=12.19.0
azure-identity>=1.15.0
azure-keyvault-secrets>=4.7.0
```

### 2.2 Create Azure-specific Utils

I'll create `app/azure_utils.py` for you with Azure Blob Storage integration.

### 2.3 Update Environment Variables

Create `.env.azure`:
```bash
# OpenAI
OPENAI_API_KEY=sk-proj-your-key

# Azure Storage
AZURE_STORAGE_ACCOUNT_NAME=your-storage-account
AZURE_STORAGE_ACCOUNT_KEY=your-storage-key
AZURE_STORAGE_CONNECTION_STRING=your-connection-string
AZURE_CONTAINER_NAME=documents
AZURE_CHROMADB_CONTAINER=chromadb

# App Configuration
CHAT_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small
DOC_ID=doc-001
THRESHOLD=0.15
TOP_K=6

# Azure App Service (set by platform)
# WEBSITE_HOSTNAME will be set automatically
```

---

## Step 3: Deploy to Azure App Service

### 3.1 Create Azure App Service

```bash
# Set variables
$APP_SERVICE_PLAN="asp-hr-chatbot"
$WEB_APP_NAME="hr-chatbot-$(Get-Random -Maximum 9999)"

# Create App Service Plan (B1 Basic tier)
az appservice plan create `
  --name $APP_SERVICE_PLAN `
  --resource-group $RESOURCE_GROUP `
  --sku B1 `
  --is-linux

# Create Web App
az webapp create `
  --name $WEB_APP_NAME `
  --resource-group $RESOURCE_GROUP `
  --plan $APP_SERVICE_PLAN `
  --runtime "PYTHON:3.11"

# Your app will be available at:
# https://$WEB_APP_NAME.azurewebsites.net
```

### 3.2 Configure App Settings

```bash
# Set environment variables
az webapp config appsettings set `
  --name $WEB_APP_NAME `
  --resource-group $RESOURCE_GROUP `
  --settings `
    OPENAI_API_KEY="your-openai-key" `
    CHAT_MODEL="gpt-4o-mini" `
    EMBEDDING_MODEL="text-embedding-3-small" `
    AZURE_STORAGE_ACCOUNT_NAME=$STORAGE_ACCOUNT `
    AZURE_STORAGE_ACCOUNT_KEY=$STORAGE_KEY `
    AZURE_CONTAINER_NAME="documents" `
    AZURE_CHROMADB_CONTAINER="chromadb" `
    DOC_ID="doc-001" `
    THRESHOLD="0.15" `
    TOP_K="6" `
    SCM_DO_BUILD_DURING_DEPLOYMENT="true" `
    WEBSITES_PORT="8000"
```

### 3.3 Create Deployment Files

**Create `startup.sh`:**
```bash
#!/bin/bash
python -m pip install --upgrade pip
pip install -r requirements.txt
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:8000 --timeout 120
```

**Create `.deployment`:**
```ini
[config]
SCM_DO_BUILD_DURING_DEPLOYMENT = true
```

**Create `web.config` (for Windows App Service):**
```xml
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <system.webServer>
    <handlers>
      <add name="PythonHandler" path="*" verb="*" modules="FastCgiModule" scriptProcessor="D:\home\Python311\python.exe|D:\home\site\wwwroot\startup.py" resourceType="Unspecified" requireAccess="Script"/>
    </handlers>
  </system.webServer>
</configuration>
```

### 3.4 Deploy via Git

```bash
# Configure local git for deployment
az webapp deployment source config-local-git `
  --name $WEB_APP_NAME `
  --resource-group $RESOURCE_GROUP

# Get deployment credentials
$deploymentUrl = az webapp deployment list-publishing-credentials `
  --name $WEB_APP_NAME `
  --resource-group $RESOURCE_GROUP `
  --query scmUri `
  --output tsv

# Add Azure remote
git remote add azure $deploymentUrl

# Push to Azure (this will deploy)
git push azure main
```

**Alternative: Deploy via ZIP**
```bash
# Create deployment package
Compress-Archive -Path * -DestinationPath deploy.zip

# Deploy
az webapp deployment source config-zip `
  --name $WEB_APP_NAME `
  --resource-group $RESOURCE_GROUP `
  --src deploy.zip
```

### 3.5 Enable HTTPS Only

```bash
az webapp update `
  --name $WEB_APP_NAME `
  --resource-group $RESOURCE_GROUP `
  --https-only true
```

---

## Step 4: Configure Domain and SSL

### 4.1 Default Azure Domain

Your app is automatically available at:
```
https://$WEB_APP_NAME.azurewebsites.net
```

This includes free SSL certificate!

### 4.2 Custom Domain (Optional)

**If you have your own domain:**

```bash
# Add custom domain
az webapp config hostname add `
  --webapp-name $WEB_APP_NAME `
  --resource-group $RESOURCE_GROUP `
  --hostname www.yourdomain.com

# Create SSL binding (free managed certificate)
az webapp config ssl create `
  --name $WEB_APP_NAME `
  --resource-group $RESOURCE_GROUP `
  --hostname www.yourdomain.com

# Bind SSL certificate
az webapp config ssl bind `
  --name $WEB_APP_NAME `
  --resource-group $RESOURCE_GROUP `
  --certificate-thumbprint <thumbprint> `
  --ssl-type SNI
```

**DNS Configuration:**
Add these records to your domain:
- **CNAME**: `www` → `$WEB_APP_NAME.azurewebsites.net`
- **TXT**: `asuid` → (get from Azure Portal)

---

## Step 5: Monitoring and Scaling

### 5.1 Enable Application Insights

```bash
# Create Application Insights
$APPINSIGHTS_NAME="ai-hr-chatbot"

az monitor app-insights component create `
  --app $APPINSIGHTS_NAME `
  --location $LOCATION `
  --resource-group $RESOURCE_GROUP `
  --application-type web

# Get instrumentation key
$INSTRUMENTATION_KEY=$(az monitor app-insights component show `
  --app $APPINSIGHTS_NAME `
  --resource-group $RESOURCE_GROUP `
  --query instrumentationKey `
  --output tsv)

# Configure app to use App Insights
az webapp config appsettings set `
  --name $WEB_APP_NAME `
  --resource-group $RESOURCE_GROUP `
  --settings APPINSIGHTS_INSTRUMENTATIONKEY=$INSTRUMENTATION_KEY
```

### 5.2 Configure Auto-scaling

```bash
# Enable autoscale (scale out to 3 instances when CPU > 70%)
az monitor autoscale create `
  --resource-group $RESOURCE_GROUP `
  --resource $APP_SERVICE_PLAN `
  --resource-type Microsoft.Web/serverfarms `
  --name autoscale-hr-chatbot `
  --min-count 1 `
  --max-count 3 `
  --count 1

az monitor autoscale rule create `
  --resource-group $RESOURCE_GROUP `
  --autoscale-name autoscale-hr-chatbot `
  --condition "Percentage CPU > 70 avg 5m" `
  --scale out 1
```

### 5.3 View Logs

```bash
# Enable logging
az webapp log config `
  --name $WEB_APP_NAME `
  --resource-group $RESOURCE_GROUP `
  --application-logging filesystem `
  --level information

# Stream logs
az webapp log tail `
  --name $WEB_APP_NAME `
  --resource-group $RESOURCE_GROUP
```

---

## Cost Estimation

### Monthly Costs (Estimated)

| Service | Tier | Cost/Month |
|---------|------|------------|
| **App Service** | B1 Basic (1 core, 1.75GB RAM) | ~$13 |
| **Storage Account** | Standard LRS (1GB) | ~$0.02 |
| **Application Insights** | Basic (1GB data) | Free tier |
| **Bandwidth** | First 100GB | Free |
| **OpenAI API** | Pay-as-you-go | ~$2-10 (varies) |
| **Total** | | **~$15-25/month** |

### Free Tier Alternative

Use **F1 Free tier** for App Service:
- **Cost**: $0/month
- **Limitations**: 60 min/day compute, 1GB storage
- **Best for**: Testing/demos, not production

### Cost Optimization Tips

1. **Use B1 tier** for production (better performance)
2. **Enable auto-shutdown** for non-business hours
3. **Use Azure Reserved Instances** (save up to 72%)
4. **Monitor API usage** with Application Insights

---

## Troubleshooting

### Issue: App won't start

**Solution:**
```bash
# Check logs
az webapp log tail --name $WEB_APP_NAME --resource-group $RESOURCE_GROUP

# Verify startup command
az webapp config show --name $WEB_APP_NAME --resource-group $RESOURCE_GROUP --query linuxFxVersion
```

### Issue: Module not found errors

**Solution:**
```bash
# SSH into container
az webapp ssh --name $WEB_APP_NAME --resource-group $RESOURCE_GROUP

# Verify Python version
python --version

# Reinstall dependencies
pip install -r requirements.txt
```

### Issue: Can't connect to Blob Storage

**Solution:**
```bash
# Test connection string
az storage blob list `
  --account-name $STORAGE_ACCOUNT `
  --account-key $STORAGE_KEY `
  --container-name documents

# Verify environment variables
az webapp config appsettings list `
  --name $WEB_APP_NAME `
  --resource-group $RESOURCE_GROUP
```

### Issue: ChromaDB data not persisting

**Solution:**
- Mount Azure Blob Storage as persistent volume
- Use Azure Files instead for better file system support
- Alternative: Use Azure PostgreSQL with pgvector extension

---

## Quick Start Commands Summary

```bash
# 1. Create all resources
az group create --name rg-hr-chatbot --location eastus
az storage account create --name hrchatbotstorage --resource-group rg-hr-chatbot
az appservice plan create --name asp-hr-chatbot --resource-group rg-hr-chatbot --sku B1
az webapp create --name hr-chatbot-app --resource-group rg-hr-chatbot --plan asp-hr-chatbot

# 2. Configure app
az webapp config appsettings set --name hr-chatbot-app --resource-group rg-hr-chatbot --settings @settings.json

# 3. Deploy
git remote add azure <deployment-url>
git push azure main

# 4. Open app
az webapp browse --name hr-chatbot-app --resource-group rg-hr-chatbot
```

---

## Post-Deployment Checklist

- [ ] Application accessible at Azure URL
- [ ] Can upload documents to Azure Blob Storage
- [ ] Document ingestion working
- [ ] Questions returning correct answers
- [ ] Logs visible in Azure Portal
- [ ] HTTPS enabled
- [ ] Monitoring configured
- [ ] Cost alerts set up
- [ ] Backup strategy defined

---

## Next Steps

1. **Test the deployment**: Visit your Azure URL and test the chatbot
2. **Configure monitoring**: Set up alerts for errors and high usage
3. **Set up CI/CD**: Use GitHub Actions for automated deployments
4. **Add authentication**: Implement Azure AD for user authentication
5. **Scale as needed**: Adjust App Service plan based on usage

## Support

- **Azure Documentation**: https://docs.microsoft.com/azure/
- **Azure Status**: https://status.azure.com/
- **Pricing Calculator**: https://azure.microsoft.com/pricing/calculator/

---

**Deployment Guide Version**: 1.0
**Last Updated**: 2025-09-29
**Author**: Rahul Sadhwani