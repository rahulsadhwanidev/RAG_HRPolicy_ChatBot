# Azure-Native Deployment Guide
## Complete Azure Stack: Azure OpenAI + Azure AI Search + Azure Blob Storage

This guide shows you how to deploy using **100% Azure services** instead of external OpenAI API.

---

## Architecture: Full Azure Stack

```
┌─────────────────────────────────────────────────────────────┐
│                     USER ACCESS                             │
│              https://your-app.azurewebsites.net             │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                 AZURE APP SERVICE                           │
│           (FastAPI Application - Python 3.11)               │
└─────────┬─────────────┬─────────────┬─────────────┬─────────┘
          │             │             │             │
    ┌─────▼─────┐ ┌────▼────┐  ┌─────▼──────┐ ┌───▼────────┐
    │   Azure   │ │ Azure   │  │   Azure    │ │   Azure    │
    │   Blob    │ │ OpenAI  │  │ AI Search  │ │    Key     │
    │  Storage  │ │ Service │  │ (Vectors)  │ │   Vault    │
    │           │ │         │  │            │ │            │
    │ • PDFs    │ │ • GPT-4 │  │ • Embeddings│ │ • Secrets  │
    │ • Docs    │ │ • Chat  │  │ • Search   │ │ • API Keys │
    └───────────┘ └─────────┘  └────────────┘ └────────────┘
```

---

## Why Use Azure-Native Services?

### Benefits

✅ **Enterprise Security**: All data stays in your Azure tenant
✅ **Compliance**: GDPR, HIPAA, SOC 2 compliant
✅ **Private Network**: No data leaves Azure
✅ **SLA Guarantees**: 99.9% uptime
✅ **Centralized Billing**: Single Azure invoice
✅ **Better Integration**: Native Azure SDKs
✅ **Regional Data**: Keep data in specific regions
✅ **Cost Optimization**: Azure Reserved Instances

### Services We'll Use

| Service | Purpose | Replaces |
|---------|---------|----------|
| **Azure OpenAI Service** | Chat completions + embeddings | OpenAI API |
| **Azure AI Search** | Vector search | ChromaDB |
| **Azure Blob Storage** | Document storage | AWS S3 |
| **Azure App Service** | Host application | EC2/ECS |
| **Azure Key Vault** | Secrets management | .env files |
| **Application Insights** | Monitoring | Custom logging |

---

## Prerequisites

1. **Azure Subscription** with:
   - Azure OpenAI Service access (requires approval)
   - Contributor role on subscription

2. **Azure CLI** installed

3. **Apply for Azure OpenAI Access**:
   - Go to: https://aka.ms/oai/access
   - Fill out the form
   - Wait for approval (usually 1-2 business days)

---

## Step 1: Create Azure OpenAI Service

### 1.1 Check if you have access

```bash
# Login
az login

# List available providers
az provider show --namespace Microsoft.CognitiveServices --query "registrationState"
```

### 1.2 Create Azure OpenAI resource

```bash
# Set variables
$RESOURCE_GROUP="rg-hr-chatbot"
$LOCATION="eastus"  # Azure OpenAI available in: eastus, southcentralus, westeurope
$OPENAI_NAME="openai-hr-chatbot-$(Get-Random -Maximum 9999)"

# Create Azure OpenAI resource
az cognitiveservices account create `
  --name $OPENAI_NAME `
  --resource-group $RESOURCE_GROUP `
  --location $LOCATION `
  --kind OpenAI `
  --sku S0 `
  --custom-domain $OPENAI_NAME
```

### 1.3 Deploy models

You need TWO models:
1. **GPT-4o-mini** for chat completions
2. **text-embedding-3-small** for embeddings

```bash
# Deploy GPT-4o-mini
az cognitiveservices account deployment create `
  --name $OPENAI_NAME `
  --resource-group $RESOURCE_GROUP `
  --deployment-name gpt-4o-mini `
  --model-name gpt-4o-mini `
  --model-version "2024-07-18" `
  --model-format OpenAI `
  --sku-capacity 10 `
  --sku-name "Standard"

# Deploy text-embedding-3-small
az cognitiveservices account deployment create `
  --name $OPENAI_NAME `
  --resource-group $RESOURCE_GROUP `
  --deployment-name text-embedding-3-small `
  --model-name text-embedding-3-small `
  --model-version "1" `
  --model-format OpenAI `
  --sku-capacity 10 `
  --sku-name "Standard"
```

### 1.4 Get Azure OpenAI credentials

```bash
# Get endpoint
$AZURE_OPENAI_ENDPOINT=$(az cognitiveservices account show `
  --name $OPENAI_NAME `
  --resource-group $RESOURCE_GROUP `
  --query properties.endpoint `
  --output tsv)

# Get API key
$AZURE_OPENAI_KEY=$(az cognitiveservices account keys list `
  --name $OPENAI_NAME `
  --resource-group $RESOURCE_GROUP `
  --query key1 `
  --output tsv)

Write-Host "Azure OpenAI Endpoint: $AZURE_OPENAI_ENDPOINT"
Write-Host "Azure OpenAI Key: $AZURE_OPENAI_KEY"
```

---

## Step 2: Create Azure AI Search (Vector Database)

### 2.1 Create search service

```bash
$SEARCH_NAME="search-hr-chatbot-$(Get-Random -Maximum 9999)"

# Create Azure AI Search
az search service create `
  --name $SEARCH_NAME `
  --resource-group $RESOURCE_GROUP `
  --location $LOCATION `
  --sku Basic `
  --partition-count 1 `
  --replica-count 1

# Get admin key
$SEARCH_KEY=$(az search admin-key show `
  --service-name $SEARCH_NAME `
  --resource-group $RESOURCE_GROUP `
  --query primaryKey `
  --output tsv)

Write-Host "Search Service: $SEARCH_NAME"
Write-Host "Search Key: $SEARCH_KEY"
```

### 2.2 Why Azure AI Search instead of ChromaDB?

- ✅ **Native vector search** with HNSW algorithm
- ✅ **Persistent storage** (no local database needed)
- ✅ **Scalable** to millions of documents
- ✅ **Enterprise features** (backups, geo-replication)
- ✅ **Integrated monitoring** with Azure
- ✅ **Pay-as-you-go** pricing

---

## Step 3: Create Azure Blob Storage

```bash
$STORAGE_ACCOUNT="hrchatbot$(Get-Random -Maximum 9999)"

# Create storage account
az storage account create `
  --name $STORAGE_ACCOUNT `
  --resource-group $RESOURCE_GROUP `
  --location $LOCATION `
  --sku Standard_LRS `
  --kind StorageV2

# Get connection string
$STORAGE_CONNECTION=$(az storage account show-connection-string `
  --name $STORAGE_ACCOUNT `
  --resource-group $RESOURCE_GROUP `
  --output tsv)

# Create containers
$STORAGE_KEY=$(az storage account keys list `
  --resource-group $RESOURCE_GROUP `
  --account-name $STORAGE_ACCOUNT `
  --query '[0].value' `
  --output tsv)

az storage container create `
  --name documents `
  --account-name $STORAGE_ACCOUNT `
  --account-key $STORAGE_KEY
```

---

## Step 4: Create Azure Key Vault (Secrets Management)

```bash
$KEYVAULT_NAME="kv-hr-chatbot-$(Get-Random -Maximum 9999)"

# Create Key Vault
az keyvault create `
  --name $KEYVAULT_NAME `
  --resource-group $RESOURCE_GROUP `
  --location $LOCATION

# Store secrets
az keyvault secret set --vault-name $KEYVAULT_NAME --name "AzureOpenAIKey" --value $AZURE_OPENAI_KEY
az keyvault secret set --vault-name $KEYVAULT_NAME --name "SearchKey" --value $SEARCH_KEY
az keyvault secret set --vault-name $KEYVAULT_NAME --name "StorageConnection" --value $STORAGE_CONNECTION
```

---

## Step 5: Update Application Code

### 5.1 Update requirements.txt

Add Azure SDK packages:

```txt
# Azure OpenAI
openai>=1.0.0
azure-identity>=1.15.0

# Azure AI Search (Vector DB)
azure-search-documents>=11.4.0

# Azure Storage
azure-storage-blob>=12.19.0

# Azure Key Vault
azure-keyvault-secrets>=4.7.0

# Existing packages
fastapi
uvicorn[standard]
pydantic==2.8.2
pypdf
tiktoken
gunicorn
python-dotenv
```

### 5.2 Create Azure-native utils

I'll create `app/azure_native_utils.py` for you with:
- Azure OpenAI integration
- Azure AI Search for vectors
- Azure Blob Storage for documents
- Azure Key Vault for secrets

---

## Step 6: Deploy Application

### 6.1 Create App Service

```bash
$APP_NAME="hr-chatbot-$(Get-Random -Maximum 9999)"
$PLAN_NAME="asp-hr-chatbot"

# Create App Service Plan
az appservice plan create `
  --name $PLAN_NAME `
  --resource-group $RESOURCE_GROUP `
  --sku B1 `
  --is-linux

# Create Web App
az webapp create `
  --name $APP_NAME `
  --resource-group $RESOURCE_GROUP `
  --plan $PLAN_NAME `
  --runtime "PYTHON:3.11"

# Get Web App identity
az webapp identity assign `
  --name $APP_NAME `
  --resource-group $RESOURCE_GROUP

$IDENTITY=$(az webapp identity show `
  --name $APP_NAME `
  --resource-group $RESOURCE_GROUP `
  --query principalId `
  --output tsv)

# Grant Key Vault access to Web App
az keyvault set-policy `
  --name $KEYVAULT_NAME `
  --object-id $IDENTITY `
  --secret-permissions get list
```

### 6.2 Configure App Settings

```bash
az webapp config appsettings set `
  --name $APP_NAME `
  --resource-group $RESOURCE_GROUP `
  --settings `
    AZURE_OPENAI_ENDPOINT="$AZURE_OPENAI_ENDPOINT" `
    AZURE_OPENAI_DEPLOYMENT_CHAT="gpt-4o-mini" `
    AZURE_OPENAI_DEPLOYMENT_EMBED="text-embedding-3-small" `
    AZURE_SEARCH_ENDPOINT="https://$SEARCH_NAME.search.windows.net" `
    AZURE_SEARCH_INDEX="hr-policy-chunks" `
    AZURE_STORAGE_CONNECTION_STRING="$STORAGE_CONNECTION" `
    AZURE_KEYVAULT_URI="https://$KEYVAULT_NAME.vault.azure.net/" `
    DOC_ID="doc-001" `
    THRESHOLD="0.15" `
    TOP_K="6" `
    WEBSITES_PORT="8000" `
    SCM_DO_BUILD_DURING_DEPLOYMENT="true"

# Enable HTTPS
az webapp update `
  --name $APP_NAME `
  --resource-group $RESOURCE_GROUP `
  --https-only true
```

---

## Step 7: Deploy Code

```bash
# Create deployment package
Compress-Archive -Path app,web,requirements.txt,startup.sh -DestinationPath deploy.zip -Force

# Deploy
az webapp deployment source config-zip `
  --name $APP_NAME `
  --resource-group $RESOURCE_GROUP `
  --src deploy.zip

# Restart to apply changes
az webapp restart `
  --name $APP_NAME `
  --resource-group $RESOURCE_GROUP

Remove-Item deploy.zip
```

---

## Cost Breakdown (Full Azure Stack)

### Monthly Costs

| Service | Tier | Usage | Cost/Month |
|---------|------|-------|------------|
| **Azure OpenAI** | S0 | ~1M tokens/month | ~$15 |
| **Azure AI Search** | Basic | 1 partition, 1 replica | ~$75 |
| **Azure Blob Storage** | Standard LRS | 1GB | ~$0.02 |
| **Azure App Service** | B1 | 1 instance | ~$13 |
| **Azure Key Vault** | Standard | <10k operations | ~$0.03 |
| **Application Insights** | Basic | 1GB data | Free |
| **Bandwidth** | Outbound | <5GB | Free |
| **Total** | | | **~$103/month** |

### Cost Optimization

1. **Use Standard tier for AI Search**: ~$250/month but better performance
2. **Reserved Instances**: Save up to 72% with 1-year commitment
3. **Dev/Test pricing**: 20% discount for non-production
4. **Free tier AI Search**: $0 but limited (50MB, 10k docs)

### Alternative: Budget-Friendly Stack

| Service | Tier | Cost/Month |
|---------|------|------------|
| Azure OpenAI | Pay-as-you-go | ~$5-10 |
| **ChromaDB on App Service** | Use local DB | $0 |
| Azure Blob Storage | Standard | ~$0.02 |
| Azure App Service | B1 | ~$13 |
| **Total** | | **~$18-23/month** |

---

## Architecture Decision: AI Search vs ChromaDB

### Option 1: Azure AI Search (Enterprise)

**Pros:**
- ✅ Fully managed, scalable
- ✅ Advanced features (filters, facets)
- ✅ Enterprise SLA
- ✅ Geo-replication

**Cons:**
- ❌ More expensive (~$75/month minimum)
- ❌ Requires index management

**Best for:** Production, >10k documents, multiple users

### Option 2: ChromaDB on App Service (Cost-Effective)

**Pros:**
- ✅ Much cheaper (~$0/month extra)
- ✅ Simple setup
- ✅ Works great for small datasets

**Cons:**
- ❌ Not scalable beyond single instance
- ❌ Data stored on app filesystem
- ❌ Lost on container restart (unless using mounted storage)

**Best for:** Development, <10k documents, budget-conscious

---

## Complete Deployment Script

I'll create `deploy_azure_native.ps1` that:
1. Creates all Azure resources
2. Deploys models to Azure OpenAI
3. Configures AI Search
4. Sets up Key Vault
5. Deploys application
6. Runs health checks

---

## Monitoring & Operations

### View logs
```bash
az webapp log tail --name $APP_NAME --resource-group $RESOURCE_GROUP
```

### Monitor costs
```bash
# View cost analysis
az consumption usage list --start-date 2025-09-01 --end-date 2025-09-30
```

### Scale up
```bash
# Upgrade to Standard tier for production
az appservice plan update `
  --name $PLAN_NAME `
  --resource-group $RESOURCE_GROUP `
  --sku S1
```

---

## Security Best Practices

1. **Managed Identities**: ✅ App Service uses managed identity (no passwords)
2. **Key Vault**: ✅ All secrets in Key Vault
3. **Private Endpoints**: Consider for production
4. **Network isolation**: Use VNet integration
5. **Azure AD Auth**: Add user authentication

---

## Next Steps

1. **Apply for Azure OpenAI access**: https://aka.ms/oai/access
2. **Run deployment script**: `.\deploy_azure_native.ps1`
3. **Upload documents**: To Azure Blob Storage
4. **Test application**: Visit your Azure URL
5. **Monitor usage**: Azure Portal → Cost Management

---

## Comparison: Azure-Native vs Hybrid

| Aspect | Hybrid (OpenAI API) | Azure-Native |
|--------|-------------------|--------------|
| **Cost** | ~$15/month | ~$103/month |
| **Setup** | Easier | More complex |
| **Security** | Data leaves Azure | All in Azure |
| **Compliance** | Standard | Enterprise |
| **Scalability** | Limited | Unlimited |
| **SLA** | None | 99.9% |
| **Best for** | Startups, MVPs | Enterprises |

---

## Support Resources

- **Azure OpenAI Docs**: https://learn.microsoft.com/azure/ai-services/openai/
- **Azure AI Search**: https://learn.microsoft.com/azure/search/
- **Pricing Calculator**: https://azure.microsoft.com/pricing/calculator/
- **Azure Support**: https://azure.microsoft.com/support/

---

**Ready to deploy?** Continue to the next step where I'll create the automated deployment script!