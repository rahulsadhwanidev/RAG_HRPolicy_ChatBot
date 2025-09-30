# Step-by-Step: Deploy with Full Azure-Native Services

**Complete guide from zero to live application with Azure OpenAI, Azure AI Search, and Azure Blob Storage.**

---

## 📋 What You'll Create

By the end of this guide, you'll have:

```
✅ Azure Resource Group (container for all resources)
✅ Azure Storage Account (for PDF documents)
✅ Azure OpenAI Service (GPT-4o-mini + embeddings)
✅ Azure AI Search (vector database)
✅ Azure Key Vault (secrets management)
✅ Azure App Service (hosting your application)
✅ Live URL where everyone can access the chatbot
```

**Estimated Time:** 30-45 minutes
**Estimated Cost:** ~$103/month

---

## 🎯 Prerequisites

Before we start, you need:

1. ✅ Azure account with admin rights (you have this!)
2. ✅ Azure OpenAI access (we'll apply for this if needed)
3. ✅ PDF documents to upload
4. ✅ Windows PowerShell

---

## Phase 1: Initial Setup (10 minutes)

### Step 1.1: Install Azure CLI

**Open PowerShell as Administrator** and run:

```powershell
# Install Azure CLI
winget install Microsoft.AzureCLI
```

**Alternative:** Download installer from https://aka.ms/installazurecliwindows

**Verify installation:**
```powershell
# Close and reopen PowerShell, then run:
az --version
```

You should see version information.

---

### Step 1.2: Login to Azure

```powershell
# Login with your org account
az login
```

**What happens:**
- Browser window opens
- Login with your organization account
- Browser shows "Authentication complete"
- Return to PowerShell

**Verify you're logged in:**
```powershell
# Show your account info
az account show

# List available subscriptions
az account list --output table
```

**If you have multiple subscriptions, set the one you want to use:**
```powershell
az account set --subscription "Your-Subscription-Name"
```

---

### Step 1.3: Check Azure OpenAI Access

```powershell
# Check if Azure OpenAI is available
az provider show --namespace Microsoft.CognitiveServices --query "registrationState"
```

**If output is "Registered":** ✅ You're good to go!

**If output is "NotRegistered":**
```powershell
# Register the provider (you're admin, so this should work)
az provider register --namespace Microsoft.CognitiveServices

# Wait 2-3 minutes, then check again
az provider show --namespace Microsoft.CognitiveServices --query "registrationState"
```

**Check if Azure OpenAI is available in your region:**
```powershell
az cognitiveservices account list-skus `
  --location eastus `
  --query "[?name=='S0' && kind=='OpenAI']"
```

**If it returns empty or error:**
You need to apply for Azure OpenAI access:
1. Go to: https://aka.ms/oai/access
2. Fill out the form with your organization details
3. Wait 1-2 business days for approval
4. Check your email for approval confirmation

**For now, we'll continue with setup. If you don't have OpenAI access yet, the script will prompt you to use regular OpenAI API instead.**

---

## Phase 2: Automated Deployment (15-20 minutes)

Now we'll run the automated deployment script that creates everything for you!

### Step 2.1: Navigate to Project Folder

```powershell
cd C:\Users\rahul\Desktop\RAG-Azure
```

### Step 2.2: Run the Deployment Script

```powershell
.\deploy_azure_native.ps1
```

**What the script will do:**
```
1. Login check ✓
2. Create Resource Group
3. Create Storage Account + Containers
4. Create Azure OpenAI Service
5. Deploy GPT-4o-mini model
6. Deploy text-embedding-3-small model
7. Create Azure AI Search
8. Create Azure Key Vault
9. Create App Service
10. Configure all settings
11. Deploy your application
```

---

### Step 2.3: Script Prompts (What to Enter)

The script will ask you several questions:

**Prompt 1: Location**
```
Location (default: eastus): [Press Enter]
```
✅ **Press Enter** to use default `eastus`

**Or choose from:**
- `eastus` (Virginia, USA)
- `westeurope` (Netherlands)
- `southcentralus` (Texas, USA)

---

**Prompt 2: Deploy Azure AI Search?**
```
Deploy Azure AI Search? (~$75/month) or use ChromaDB ($0)? (search/chromadb):
```

✅ **Type:** `search`

**Why?**
- Azure AI Search = Scalable, enterprise-grade vector database
- ChromaDB = Local, works but not scalable for production

---

**Prompt 3: Confirmation**
```
Proceed with deployment? (yes/no):
```

✅ **Type:** `yes`

---

**If Azure OpenAI is not available, it will ask:**
```
Enter OpenAI API Key (or press Enter to skip):
```

**Option A:** If you have OpenAI API key:
1. Go to https://platform.openai.com/api-keys
2. Create new key
3. Copy and paste it here

**Option B:** If waiting for Azure OpenAI approval:
- Press Enter to skip
- Script will continue without AI (you can add it later)

---

### Step 2.4: Wait for Deployment

**The script will now create everything. You'll see:**

```powershell
[1/8] Creating Resource Group...
[OK] Resource Group created

[2/8] Creating Azure Blob Storage...
[OK] Storage Account created: hrchatbot1234

[3/8] Creating Azure OpenAI Service...
  Deploying GPT-4o-mini model...
  Deploying text-embedding-3-small model...
[OK] Azure OpenAI created: openai-hr-5678

[4/8] Creating Azure AI Search...
[OK] Azure AI Search created: search-hr-9012

[5/8] Creating Azure Key Vault...
[OK] Key Vault created: kv-hr-3456

[6/8] Creating Azure App Service...
[OK] App Service created: hr-chatbot-7890

[7/8] Configuring Application...
[OK] Application configured

[8/8] Deploying Application Code...
[OK] Application deployed
```

**Wait 15-20 minutes for everything to complete.**

---

### Step 2.5: Save the Output

**At the end, you'll see:**

```
================================================
 Deployment Complete!
================================================

Application URL:
  https://hr-chatbot-7890.azurewebsites.net

Web UI:
  https://hr-chatbot-7890.azurewebsites.net/ui

API Docs:
  https://hr-chatbot-7890.azurewebsites.net/docs

Azure Resources Created:
  Resource Group: rg-hr-chatbot
  Storage Account: hrchatbot1234
  Azure OpenAI: openai-hr-5678
  Azure AI Search: search-hr-9012
  Key Vault: kv-hr-3456
  App Service: hr-chatbot-7890

Estimated monthly cost: ~$103
```

**📝 IMPORTANT:** Copy and save these names, especially:
- Storage Account name
- Your application URL

---

## Phase 3: Configure Azure Search Index (5 minutes)

The Azure AI Search service is created, but we need to set up the index.

### Step 3.1: Open Azure Portal

1. Go to https://portal.azure.com
2. Login with your org account

### Step 3.2: Find Your Search Service

1. Click **"Search"** at the top
2. Type: `search-hr-` (your search service name)
3. Click on your **Azure AI Search** service

### Step 3.3: Create Search Index (via API)

Actually, **the application will create the index automatically** on first document upload!

So you can skip this step. The index will be created when you upload documents.

---

## Phase 4: Upload Documents (10 minutes)

Now let's upload your HR policy documents.

### Method A: Using Azure Portal (Easiest)

#### Step 4.1: Navigate to Storage Account

1. In Azure Portal (https://portal.azure.com)
2. Click **"Storage accounts"** in the left menu
3. Click your storage account (e.g., `hrchatbot1234`)

#### Step 4.2: Upload PDF Document

1. Click **"Containers"** in the left menu
2. Click **"documents"** container
3. Click **"Upload"** button at the top
4. Click **"Browse for files"**
5. Select your PDF file (e.g., `HR_Policy.pdf`)
6. **IMPORTANT:** In "Advanced" section:
   - Set "Upload to folder": `doc-001/`
7. Click **"Upload"**

**Result:** Your file is at `doc-001/your-file.pdf`

#### Step 4.3: Create Manifest File

1. On your computer, create a file named `manifest.json`
2. Open it in Notepad and paste:

```json
{
  "latest_pdf": "doc-001/HR_Policy.pdf"
}
```

**Replace `HR_Policy.pdf` with your actual filename!**

3. Save the file
4. Go back to Azure Portal → Storage → Containers → documents
5. Click **"Upload"**
6. Browse and select `manifest.json`
7. In "Advanced" section, set "Upload to folder": `doc-001/`
8. Click **"Upload"**

**Result:** You now have:
- ✅ `doc-001/HR_Policy.pdf`
- ✅ `doc-001/manifest.json`

---

### Method B: Using Azure CLI

```powershell
# Set your storage account name (from deployment output)
$STORAGE_ACCOUNT="hrchatbot1234"  # REPLACE with your actual name
$RESOURCE_GROUP="rg-hr-chatbot"

# Upload PDF
az storage blob upload `
  --account-name $STORAGE_ACCOUNT `
  --container-name documents `
  --name "doc-001/HR_Policy.pdf" `
  --file "C:\path\to\your\HR_Policy.pdf" `
  --auth-mode login

# Create manifest file
@"
{
  "latest_pdf": "doc-001/HR_Policy.pdf"
}
"@ | Out-File manifest.json -Encoding utf8

# Upload manifest
az storage blob upload `
  --account-name $STORAGE_ACCOUNT `
  --container-name documents `
  --name "doc-001/manifest.json" `
  --file manifest.json `
  --auth-mode login

# Clean up local file
Remove-Item manifest.json
```

---

## Phase 5: Test Your Application (5 minutes)

### Step 5.1: Open the Web UI

Open your browser and go to:
```
https://hr-chatbot-7890.azurewebsites.net/ui
```

*Replace `hr-chatbot-7890` with your actual app name from deployment output*

**You should see:**
- A professional chat interface
- "HR Policy Chatbot" title
- Text input box
- Send button

---

### Step 5.2: Refresh Documents

**Option A: Via Web UI**
- Look for a "Refresh Documents" button
- Click it

**Option B: Via URL**
Open in browser:
```
https://hr-chatbot-7890.azurewebsites.net/refresh
```

**You should see:**
```json
{
  "ok": true,
  "s3_key": "doc-001/HR_Policy.pdf",
  "pages": 24,
  "chunks": 42,
  "action": "reingested"
}
```

This means:
- ✅ Document downloaded from storage
- ✅ Processed into 24 pages
- ✅ Split into 42 chunks
- ✅ Embeddings created
- ✅ Uploaded to Azure AI Search
- ✅ Ready for questions!

**If you see an error:**
- Check that your PDF file is uploaded correctly
- Check that manifest.json has the correct filename
- Wait 2-3 minutes and try again (app might still be starting)

---

### Step 5.3: Ask Your First Question

In the chat interface, type:
```
What is the vacation policy?
```

Press **Send** or hit **Enter**.

**You should get:**
- An answer based on your document
- Page number citations (e.g., "According to page 12...")
- The answer should be specific to YOUR document

**Try more questions:**
```
How many sick days do I get?
What are the working hours?
How do I request time off?
```

---

### Step 5.4: Check Conversation History

Ask a follow-up question:
```
Can I carry over unused vacation days?
```

The chatbot should understand you're still talking about vacation, even though you didn't mention "vacation" in this question. This tests the conversation memory!

---

## Phase 6: Verify Everything Works (5 minutes)

### Check 1: Health Endpoint

Visit:
```
https://hr-chatbot-7890.azurewebsites.net/health
```

**Expected output:**
```json
{
  "status": "healthy",
  "storage": "Azure Blob Storage",
  "doc_id": "doc-001",
  "last_ingested_key": "doc-001/HR_Policy.pdf",
  "pages": 24,
  "chunks": 42
}
```

✅ All green? Perfect!

---

### Check 2: API Documentation

Visit:
```
https://hr-chatbot-7890.azurewebsites.net/docs
```

**You should see:**
- Swagger/OpenAPI interface
- List of all API endpoints
- Try them out interactively

---

### Check 3: Azure Portal - View Logs

1. Go to https://portal.azure.com
2. Navigate to **App Services**
3. Click your app (e.g., `hr-chatbot-7890`)
4. Click **"Log stream"** in the left menu

**You should see real-time logs:**
```
[QUESTION] NEW QUESTION RECEIVED
Question: 'What is the vacation policy?'
[OK] Document sync: noop
[EMBED] Generating question embedding...
[OK] Embedding generated
[SEARCH] Searching vector database...
[OK] Found 6 results
[LLM] Calling LLM...
[OK] LLM response received
[SUCCESS] Question answered
```

---

## Phase 7: Share with Your Team

### Step 7.1: Get the Public URL

Your application is now live at:
```
https://hr-chatbot-7890.azurewebsites.net/ui
```

**This URL is:**
- ✅ Publicly accessible (anyone with link can use it)
- ✅ HTTPS secured (SSL certificate included)
- ✅ Always on (24/7 availability)

### Step 7.2: Share with Team

Send this message to your team:

```
Hi Team,

Our new HR Policy Chatbot is now live! 🎉

Access it here:
https://hr-chatbot-7890.azurewebsites.net/ui

You can ask questions like:
- "What is the vacation policy?"
- "How many sick days do I get?"
- "What are the working hours?"

The chatbot will answer based on our official HR policy documents and cite specific page numbers.

Let me know if you have any questions!
```

---

## Phase 8: Advanced Configuration (Optional)

### Add Custom Domain (Optional)

If you want to use your own domain (e.g., `hr-bot.yourcompany.com`):

```powershell
# Add custom domain
az webapp config hostname add `
  --webapp-name hr-chatbot-7890 `
  --resource-group rg-hr-chatbot `
  --hostname hr-bot.yourcompany.com

# Enable SSL (free managed certificate)
az webapp config ssl create `
  --name hr-chatbot-7890 `
  --resource-group rg-hr-chatbot `
  --hostname hr-bot.yourcompany.com
```

**You'll also need to:**
1. Add DNS records in your domain registrar:
   - CNAME: `hr-bot` → `hr-chatbot-7890.azurewebsites.net`
   - TXT: `asuid.hr-bot` → (verification ID from Azure)

---

### Enable Authentication (Optional)

To restrict access to your organization only:

1. In Azure Portal, go to your App Service
2. Click **"Authentication"** in the left menu
3. Click **"Add identity provider"**
4. Select **"Microsoft"**
5. Choose **"Workforce configuration (current tenant)"**
6. Click **"Add"**

**Now only users in your Azure AD can access the chatbot!**

---

### Set Up Cost Alerts

```powershell
# Create budget alert at $150/month
az consumption budget create `
  --budget-name "hr-chatbot-budget" `
  --amount 150 `
  --resource-group rg-hr-chatbot `
  --time-grain Monthly `
  --time-period-start-date (Get-Date -Format "yyyy-MM-01") `
  --time-period-end-date (Get-Date -Format "yyyy-MM-01").AddYears(1)
```

---

## 🎯 Success Checklist

Go through this checklist to confirm everything is working:

- [ ] Azure CLI installed and logged in
- [ ] All Azure resources created (8 resources)
- [ ] Application deployed successfully
- [ ] PDF documents uploaded to storage
- [ ] manifest.json created and uploaded
- [ ] Document ingestion successful (via /refresh)
- [ ] Can ask questions and get answers
- [ ] Answers include page citations
- [ ] Conversation history works (follow-up questions)
- [ ] Health endpoint returns status
- [ ] API docs accessible at /docs
- [ ] Logs visible in Azure Portal
- [ ] URL shared with team

---

## 💰 Cost Breakdown

Your monthly costs will be approximately:

| Service | Tier | Cost/Month |
|---------|------|------------|
| Azure OpenAI | Pay-as-you-go | ~$15 |
| Azure AI Search | Basic (15GB) | ~$75 |
| Azure Blob Storage | Standard LRS | ~$0.02 |
| Azure App Service | B1 (Basic) | ~$13 |
| Azure Key Vault | Standard | ~$0.03 |
| **Total** | | **~$103** |

**View actual costs:**
1. Go to Azure Portal
2. Navigate to **Cost Management + Billing**
3. Click **Cost analysis**
4. Filter by: Resource Group = `rg-hr-chatbot`

---

## 🔍 Troubleshooting

### Issue: Script says "Azure OpenAI not available"

**Solution:**
1. Apply for access: https://aka.ms/oai/access
2. While waiting, use OpenAI API:
   - Get key from https://platform.openai.com/api-keys
   - When script asks, paste the key
3. After approval, redeploy with: `.\deploy_azure_native.ps1 -Force`

---

### Issue: "I don't know" responses

**Causes:**
1. Document not uploaded correctly
2. Manifest.json has wrong filename
3. Similarity threshold too high

**Solutions:**
```powershell
# Check if document exists
az storage blob list `
  --account-name hrchatbot1234 `
  --container-name documents `
  --auth-mode login

# Re-upload document
# Re-trigger ingestion at /refresh

# Try debug endpoint
https://hr-chatbot-7890.azurewebsites.net/debug_search
```

---

### Issue: App not starting

**Check logs:**
```powershell
az webapp log tail `
  --name hr-chatbot-7890 `
  --resource-group rg-hr-chatbot
```

**Restart app:**
```powershell
az webapp restart `
  --name hr-chatbot-7890 `
  --resource-group rg-hr-chatbot
```

---

### Issue: High costs

**Optimize:**
```powershell
# Downgrade App Service (if low traffic)
az appservice plan update `
  --name asp-hr-chatbot `
  --resource-group rg-hr-chatbot `
  --sku F1  # Free tier (limited)

# Use ChromaDB instead of AI Search
# Redeploy with: .\deploy_azure.ps1 instead
```

---

## 📞 Need More Help?

**View comprehensive guides:**
- Full deployment: `AZURE_NATIVE_DEPLOYMENT.md`
- Troubleshooting: `DEPLOY_NOW.md`
- Architecture: `TECHNICAL_DOCUMENTATION.md`

**Check Azure resources:**
```powershell
# List all resources
az resource list --resource-group rg-hr-chatbot --output table

# Check app status
az webapp show `
  --name hr-chatbot-7890 `
  --resource-group rg-hr-chatbot `
  --query state
```

---

## 🎉 Congratulations!

You now have a fully functional, production-ready HR Policy Chatbot running on Azure with:

✅ **Azure OpenAI** for intelligent responses
✅ **Azure AI Search** for fast vector search
✅ **Azure Blob Storage** for document management
✅ **Azure App Service** for reliable hosting
✅ **HTTPS enabled** for security
✅ **Publicly accessible** for your team

**Your chatbot is live at:**
```
https://hr-chatbot-7890.azurewebsites.net/ui
```

**Share it with your team and start answering HR questions automatically!** 🚀