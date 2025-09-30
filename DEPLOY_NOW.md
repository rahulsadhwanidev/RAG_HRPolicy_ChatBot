# Quick Deployment Guide - You Have Admin Access!

Since you have admin rights to your Azure org, here's the fastest path to deployment.

---

## ⚡ 5-Minute Setup

### Step 1: Install Azure CLI (if not installed)

**Windows PowerShell (as Administrator):**
```powershell
winget install Microsoft.AzureCLI
```

**Or download installer:**
https://aka.ms/installazurecliwindows

**Verify installation:**
```powershell
az --version
```

---

### Step 2: Login to Azure

```powershell
# Login with your org account
az login

# Verify you're logged in
az account show

# List available subscriptions
az account list --output table

# Set the subscription you want to use (if you have multiple)
az account set --subscription "Your-Subscription-Name"
```

---

### Step 3: Check Azure OpenAI Access

Since you have admin rights, check if Azure OpenAI is already enabled:

```powershell
# Check if Azure OpenAI provider is registered
az provider show --namespace Microsoft.CognitiveServices --query "registrationState"
```

**If it shows "NotRegistered":**
```powershell
# Register the provider (you have admin rights!)
az provider register --namespace Microsoft.CognitiveServices
```

**Check available regions for Azure OpenAI:**
```powershell
az cognitiveservices account list-skus --location eastus --query "[?name=='S0' && kind=='OpenAI']"
```

If Azure OpenAI is not available, you have TWO options:

**Option A:** Apply for access (1-2 days): https://aka.ms/oai/access
**Option B:** Use the Hybrid approach with regular OpenAI API (deploy today!)

---

## 🚀 Deployment Options

### Option 1: Full Azure Stack (Recommended if you have OpenAI access)

**Cost:** ~$103/month
**Features:** Azure OpenAI, Azure AI Search, fully managed

```powershell
cd C:\Users\rahul\Desktop\RAG-Azure
.\deploy_azure_native.ps1
```

This will:
1. ✅ Create all Azure resources
2. ✅ Deploy Azure OpenAI with models
3. ✅ Set up Azure AI Search
4. ✅ Deploy your application
5. ✅ Give you a live URL

**Estimated time:** 15-20 minutes

---

### Option 2: Hybrid Approach (Deploy RIGHT NOW!)

**Cost:** ~$15-25/month
**Features:** Azure hosting, OpenAI API, ChromaDB

```powershell
cd C:\Users\rahul\Desktop\RAG-Azure
.\deploy_azure.ps1
```

This will:
1. ✅ Create Azure resources (Storage, App Service)
2. ✅ Deploy application
3. ✅ Use OpenAI API (you need API key)

**Estimated time:** 10-15 minutes

---

## 📝 Step-by-Step: Option 2 (Fastest - Deploy Now!)

Since Option 2 doesn't require Azure OpenAI approval, let's do that first:

### Step 1: Get OpenAI API Key

1. Go to https://platform.openai.com/api-keys
2. Create new secret key
3. Copy it (you'll need it during deployment)

### Step 2: Run Deployment Script

Open **PowerShell** in your project directory:

```powershell
cd C:\Users\rahul\Desktop\RAG-Azure

# Run the deployment script
.\deploy_azure.ps1
```

**The script will ask you:**
- Resource group name (press Enter for default: `rg-hr-chatbot`)
- Location (press Enter for default: `eastus`)
- Confirm deployment (type `yes`)
- OpenAI API key (paste your key)

**Wait 10-15 minutes...**

### Step 3: Script Output

At the end, you'll see:

```
Application URL:
  https://hr-chatbot-XXXX.azurewebsites.net

Web UI:
  https://hr-chatbot-XXXX.azurewebsites.net/ui

Storage Account: hrchatbotXXXX
```

✅ **Your app is now live!**

---

## 📤 Upload Your HR Policy Documents

### Option A: Using Azure Portal (Easiest)

1. Go to https://portal.azure.com
2. Navigate to **Storage accounts**
3. Click your storage account (e.g., `hrchatbotXXXX`)
4. Click **Containers** → **documents**
5. Click **Upload**
6. Upload your PDF file

**Create manifest.json:**
7. Click **Upload** again
8. Create a text file named `manifest.json` with:
   ```json
   {
     "latest_pdf": "doc-001/your-document-name.pdf"
   }
   ```
9. Upload it to the path: `doc-001/manifest.json`

### Option B: Using Azure CLI

```powershell
# Set your storage account name (from deployment output)
$STORAGE_ACCOUNT="hrchatbotXXXX"
$RESOURCE_GROUP="rg-hr-chatbot"

# Get storage key
$STORAGE_KEY=$(az storage account keys list `
  --resource-group $RESOURCE_GROUP `
  --account-name $STORAGE_ACCOUNT `
  --query '[0].value' `
  --output tsv)

# Upload your PDF
az storage blob upload `
  --account-name $STORAGE_ACCOUNT `
  --account-key $STORAGE_KEY `
  --container-name documents `
  --name "doc-001/hr-policy.pdf" `
  --file "path\to\your\policy.pdf"

# Create and upload manifest
@"
{
  "latest_pdf": "doc-001/hr-policy.pdf"
}
"@ | Out-File manifest.json -Encoding utf8

az storage blob upload `
  --account-name $STORAGE_ACCOUNT `
  --account-key $STORAGE_KEY `
  --container-name documents `
  --name "doc-001/manifest.json" `
  --file manifest.json

Remove-Item manifest.json
```

---

## 🧪 Test Your Deployment

### Step 1: Open the Web UI

Visit: `https://hr-chatbot-XXXX.azurewebsites.net/ui`

### Step 2: Trigger Document Ingestion

1. In the web UI, click **"Refresh Documents"** button
2. OR visit: `https://hr-chatbot-XXXX.azurewebsites.net/refresh`

**You should see:**
```json
{
  "ok": true,
  "s3_key": "doc-001/hr-policy.pdf",
  "pages": 24,
  "chunks": 15,
  "action": "reingested"
}
```

### Step 3: Ask a Question

In the chat interface, type:
```
What is the vacation policy?
```

**You should get an answer with page citations!**

---

## 🔍 Troubleshooting

### Issue: Deployment script not found

**Solution:**
```powershell
# Make sure you're in the right directory
cd C:\Users\rahul\Desktop\RAG-Azure

# Check if files exist
ls deploy_azure.ps1

# If missing, pull from git
git pull
```

### Issue: "Script execution is disabled"

**Solution (run PowerShell as Admin):**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Issue: App not starting

**Check logs:**
```powershell
az webapp log tail --name hr-chatbot-XXXX --resource-group rg-hr-chatbot
```

### Issue: Can't find storage account

**List all resources:**
```powershell
az resource list --resource-group rg-hr-chatbot --output table
```

---

## 📊 View Your Resources

### Azure Portal

1. Go to https://portal.azure.com
2. Click **Resource groups**
3. Click **rg-hr-chatbot**

You'll see:
- ✅ Storage account (documents)
- ✅ App Service plan (hosting plan)
- ✅ App Service (your application)

### Cost Management

To see costs:
1. In Azure Portal, go to **Cost Management + Billing**
2. Click **Cost analysis**
3. Filter by resource group: `rg-hr-chatbot`

---

## 🎯 Next Steps After Deployment

1. **Share the URL** with your team
2. **Set up custom domain** (optional):
   ```powershell
   az webapp config hostname add `
     --webapp-name hr-chatbot-XXXX `
     --resource-group rg-hr-chatbot `
     --hostname www.yourdomain.com
   ```

3. **Enable auto-scaling** (if needed):
   ```powershell
   az monitor autoscale create `
     --resource-group rg-hr-chatbot `
     --resource hr-chatbot-XXXX `
     --min-count 1 `
     --max-count 3
   ```

4. **Set up monitoring alerts**:
   - Go to Azure Portal → App Service → Alerts
   - Create alert for high CPU, memory, or errors

---

## 💰 Monitor Costs

**Current setup costs:**
- App Service (B1): ~$13/month
- Storage: ~$0.02/month
- OpenAI API: Pay-as-you-go (~$2-10/month)
- **Total: ~$15-25/month**

**Set up cost alerts:**
```powershell
# Create budget alert at $30/month
az consumption budget create `
  --budget-name "hr-chatbot-budget" `
  --amount 30 `
  --resource-group rg-hr-chatbot `
  --time-grain Monthly
```

---

## ⚡ Quick Commands Reference

```powershell
# View logs
az webapp log tail --name hr-chatbot-XXXX --resource-group rg-hr-chatbot

# Restart app
az webapp restart --name hr-chatbot-XXXX --resource-group rg-hr-chatbot

# View app settings
az webapp config appsettings list --name hr-chatbot-XXXX --resource-group rg-hr-chatbot

# Scale up (more power)
az appservice plan update --name asp-hr-chatbot --resource-group rg-hr-chatbot --sku S1

# Scale out (more instances)
az appservice plan update --name asp-hr-chatbot --resource-group rg-hr-chatbot --number-of-workers 2

# Delete everything (cleanup)
az group delete --name rg-hr-chatbot --yes --no-wait
```

---

## 🆘 Need Help?

**Check deployment logs:**
```powershell
az webapp log tail --name hr-chatbot-XXXX --resource-group rg-hr-chatbot
```

**Check app status:**
```powershell
az webapp show --name hr-chatbot-XXXX --resource-group rg-hr-chatbot --query state
```

**View all resources:**
```powershell
az resource list --resource-group rg-hr-chatbot --output table
```

---

## ✅ Deployment Checklist

- [ ] Azure CLI installed
- [ ] Logged into Azure with admin account
- [ ] OpenAI API key obtained
- [ ] Ran `.\deploy_azure.ps1`
- [ ] Uploaded PDF documents to Storage
- [ ] Created manifest.json
- [ ] Tested web UI at `/ui`
- [ ] Asked test question
- [ ] Got answer with page citations
- [ ] Shared URL with team

---

**Ready?** Open PowerShell and run:

```powershell
cd C:\Users\rahul\Desktop\RAG-Azure
.\deploy_azure.ps1
```

**Your HR chatbot will be live in 15 minutes!** 🚀