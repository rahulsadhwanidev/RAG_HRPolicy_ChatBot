# Quick Start - Deploy to Azure in 10 Minutes

This guide will help you deploy the HR Policy Chatbot to Azure quickly.

## Prerequisites

- Azure account (create free at https://azure.microsoft.com/free/)
- Azure CLI installed
- Your OpenAI API key
- PDF documents to upload

## Option 1: Automated Deployment (Recommended)

### Step 1: Run the deployment script

Open PowerShell and run:

```powershell
cd C:\Users\rahul\Desktop\RAG-Azure
.\deploy_azure.ps1
```

The script will:
1. Create all Azure resources
2. Configure settings
3. Deploy your application

**That's it!** Your app will be live at: `https://hr-chatbot-XXXX.azurewebsites.net`

## Option 2: Manual Deployment

### Step 1: Install Azure CLI

```powershell
winget install Microsoft.AzureCLI
```

### Step 2: Login to Azure

```bash
az login
```

### Step 3: Create resources

```bash
# Set variables
$RG="rg-hr-chatbot"
$LOCATION="eastus"
$STORAGE="hrchatbot$(Get-Random -Maximum 9999)"
$PLAN="asp-hr-chatbot"
$APP="hr-chatbot-$(Get-Random -Maximum 9999)"

# Create resource group
az group create --name $RG --location $LOCATION

# Create storage account
az storage account create --name $STORAGE --resource-group $RG --sku Standard_LRS

# Get storage key
$KEY=$(az storage account keys list --resource-group $RG --account-name $STORAGE --query '[0].value' -o tsv)

# Create containers
az storage container create --name documents --account-name $STORAGE --account-key $KEY
az storage container create --name chromadb --account-name $STORAGE --account-key $KEY

# Create app service
az appservice plan create --name $PLAN --resource-group $RG --sku B1 --is-linux
az webapp create --name $APP --resource-group $RG --plan $PLAN --runtime "PYTHON:3.11"

# Get connection string
$CONN=$(az storage account show-connection-string --name $STORAGE --resource-group $RG -o tsv)

# Configure app
az webapp config appsettings set --name $APP --resource-group $RG --settings `
    OPENAI_API_KEY="your-key-here" `
    AZURE_STORAGE_CONNECTION_STRING="$CONN" `
    AZURE_CONTAINER_NAME="documents" `
    DOC_ID="doc-001" `
    WEBSITES_PORT="8000"

# Enable HTTPS
az webapp update --name $APP --resource-group $RG --https-only true

# Deploy code
Compress-Archive -Path app,web,requirements.txt,startup.sh,.deployment,runtime.txt -DestinationPath deploy.zip -Force
az webapp deployment source config-zip --name $APP --resource-group $RG --src deploy.zip
```

### Step 4: Upload documents

**Option A: Azure Portal**
1. Go to https://portal.azure.com
2. Navigate to your storage account
3. Click "Containers" → "documents"
4. Upload your PDF files

**Option B: Azure CLI**
```bash
# Upload PDF
az storage blob upload `
    --account-name $STORAGE `
    --account-key $KEY `
    --container-name documents `
    --name "doc-001/1234567890.pdf" `
    --file "your-document.pdf"

# Create manifest
@"
{
  "latest_pdf": "doc-001/1234567890.pdf"
}
"@ | Out-File manifest.json -Encoding utf8

az storage blob upload `
    --account-name $STORAGE `
    --account-key $KEY `
    --container-name documents `
    --name "doc-001/manifest.json" `
    --file manifest.json
```

### Step 5: Access your app

Visit: `https://YOUR-APP-NAME.azurewebsites.net/ui`

## Verify Deployment

1. **Check health**: `https://YOUR-APP.azurewebsites.net/health`
2. **View logs**: `az webapp log tail --name $APP --resource-group $RG`
3. **Test API**: `https://YOUR-APP.azurewebsites.net/docs`

## Troubleshooting

### App not starting?
```bash
# View logs
az webapp log tail --name YOUR-APP --resource-group rg-hr-chatbot

# Restart app
az webapp restart --name YOUR-APP --resource-group rg-hr-chatbot
```

### Can't upload documents?
- Check storage account exists
- Verify container permissions
- Use Azure Storage Explorer for easier uploads

### Getting errors?
- Verify OpenAI API key is correct
- Check Azure connection string is set
- Ensure manifest.json exists in storage

## Cost

**Basic tier (B1)**: ~$13/month
- Perfect for production
- Always on
- Custom domains
- SSL included

**Free tier (F1)**: $0/month
- Good for testing
- 60 minutes/day limit
- No custom domains

## Next Steps

1. ✅ Upload your documents
2. ✅ Test the chatbot
3. ✅ Share the URL with your team
4. ✅ Monitor usage in Azure Portal
5. ✅ Set up custom domain (optional)

## Need Help?

- Full guide: [AZURE_DEPLOYMENT_GUIDE.md](./AZURE_DEPLOYMENT_GUIDE.md)
- Technical docs: [TECHNICAL_DOCUMENTATION.md](./TECHNICAL_DOCUMENTATION.md)
- GitHub repo: https://github.com/rahulsadhwanidev/RAG_HRPolicy_ChatBot

---

**Estimated time**: 10-15 minutes
**Cost**: ~$13/month (B1 tier) or $0 (F1 free tier)
**Difficulty**: Easy