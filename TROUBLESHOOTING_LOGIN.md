# Troubleshooting Azure CLI Login Issues

## Issue: Cannot login with `az login`

Multiple solutions depending on what error you're getting.

---

## Solution 1: Try Different Login Methods

### Method A: Device Code Login

If browser doesn't open or you're on a restricted machine:

```powershell
az login --use-device-code
```

**Steps:**
1. Run the command
2. You'll see: "To sign in, use a web browser to open https://microsoft.com/devicelogin and enter the code XXXXXX"
3. Open browser on ANY device (even your phone!)
4. Go to https://microsoft.com/devicelogin
5. Enter the code shown in PowerShell
6. Complete login
7. Return to PowerShell - you're now logged in!

---

### Method B: Service Principal Login

If your organization uses service principals:

```powershell
az login --service-principal `
  -u <app-id> `
  -p <password-or-cert> `
  --tenant <tenant-id>
```

Ask your Azure admin for these credentials.

---

### Method C: Managed Identity (if on Azure VM)

If you're running this from an Azure VM:

```powershell
az login --identity
```

---

## Solution 2: Use Azure Portal Instead (Manual Setup)

You can create all resources manually through Azure Portal if CLI login doesn't work!

### Step 1: Create Resource Group

1. Go to https://portal.azure.com
2. Login with your org account
3. Click **"Resource groups"** in left menu
4. Click **"+ Create"**
5. Fill in:
   - **Subscription:** Select your subscription
   - **Resource group:** `rg-hr-chatbot`
   - **Region:** East US
6. Click **"Review + create"**
7. Click **"Create"**

✅ **Resource Group Created!**

---

### Step 2: Create Storage Account

1. In Azure Portal, search for **"Storage accounts"**
2. Click **"+ Create"**
3. Fill in:
   - **Resource group:** `rg-hr-chatbot`
   - **Storage account name:** `hrchatbot` + random numbers (e.g., `hrchatbot2024`)
   - **Region:** East US
   - **Performance:** Standard
   - **Redundancy:** LRS (Locally-redundant storage)
4. Click **"Review + create"**
5. Click **"Create"**
6. Wait 1-2 minutes
7. Click **"Go to resource"**

**Create Container:**
1. Click **"Containers"** in left menu
2. Click **"+ Container"**
3. Name: `documents`
4. Click **"Create"**

✅ **Storage Created!**

---

### Step 3: Create Azure OpenAI (if you have access)

1. Search for **"Azure OpenAI"**
2. Click **"+ Create"**
3. Fill in:
   - **Resource group:** `rg-hr-chatbot`
   - **Region:** East US
   - **Name:** `openai-hr-` + random numbers
   - **Pricing tier:** Standard S0
4. Click **"Review + create"**
5. Click **"Create"**

**Deploy Models:**
1. Go to your Azure OpenAI resource
2. Click **"Model deployments"**
3. Click **"+ Create new deployment"**
4. Select model: **gpt-4o-mini**
5. Deployment name: `gpt-4o-mini`
6. Click **"Create"**
7. Repeat for: **text-embedding-3-small**

✅ **Azure OpenAI Created!**

---

### Step 4: Create Azure AI Search (Optional)

1. Search for **"Azure AI Search"**
2. Click **"+ Create"**
3. Fill in:
   - **Resource group:** `rg-hr-chatbot`
   - **Service name:** `search-hr-` + random
   - **Location:** East US
   - **Pricing tier:** Basic
4. Click **"Review + create"**
5. Click **"Create"**

✅ **AI Search Created!**

---

### Step 5: Create App Service

1. Search for **"App Services"**
2. Click **"+ Create"** → **"Web App"**
3. Fill in:
   - **Resource group:** `rg-hr-chatbot`
   - **Name:** `hr-chatbot-` + random numbers
   - **Publish:** Code
   - **Runtime stack:** Python 3.11
   - **Operating System:** Linux
   - **Region:** East US
4. Click **"Next: Deployment"**
5. Leave defaults, click **"Next: Networking"**
6. Leave defaults, click **"Review + create"**
7. Click **"Create"**

✅ **App Service Created!**

---

### Step 6: Configure App Service

1. Go to your App Service
2. Click **"Configuration"** in left menu
3. Click **"+ New application setting"**
4. Add each setting:

| Name | Value |
|------|-------|
| `AZURE_OPENAI_ENDPOINT` | `https://openai-hr-XXXX.openai.azure.com/` |
| `AZURE_OPENAI_KEY` | (From Azure OpenAI → Keys and Endpoint) |
| `AZURE_OPENAI_DEPLOYMENT_CHAT` | `gpt-4o-mini` |
| `AZURE_OPENAI_DEPLOYMENT_EMBED` | `text-embedding-3-small` |
| `AZURE_STORAGE_CONNECTION_STRING` | (From Storage → Access keys) |
| `AZURE_CONTAINER_NAME` | `documents` |
| `DOC_ID` | `doc-001` |
| `THRESHOLD` | `0.15` |
| `TOP_K` | `6` |
| `WEBSITES_PORT` | `8000` |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | `true` |

5. Click **"Save"**

---

### Step 7: Deploy Code (Manual)

**Option A: Deploy from GitHub**

1. In App Service, click **"Deployment Center"**
2. Select **"GitHub"**
3. Authorize GitHub
4. Select:
   - Organization: `rahulsadhwanidev`
   - Repository: `RAG_HRPolicy_ChatBot`
   - Branch: `main`
5. Click **"Save"**

**Option B: Deploy from Local (using VS Code)**

1. Install VS Code: https://code.visualstudio.com/
2. Install Azure App Service extension
3. Open your project folder in VS Code
4. Click Azure icon in sidebar
5. Right-click on your App Service
6. Select **"Deploy to Web App"**

---

## Solution 3: Fix CLI Login Issues

### Issue: Browser doesn't open

```powershell
# Use device code instead
az login --use-device-code
```

### Issue: "No subscriptions found"

```powershell
# List all accessible subscriptions
az account list --all --output table

# If empty, contact your Azure admin to grant access
```

### Issue: Proxy/Firewall blocking

```powershell
# Set proxy
$env:HTTP_PROXY="http://proxy.company.com:8080"
$env:HTTPS_PROXY="http://proxy.company.com:8080"

# Then try login
az login
```

### Issue: Corporate security restrictions

**Workaround:** Use Azure Cloud Shell instead!

1. Go to https://portal.azure.com
2. Click the **Cloud Shell** icon (>_) in top right
3. Select **PowerShell**
4. You're now logged in automatically!
5. Clone your repo:
   ```bash
   git clone https://github.com/rahulsadhwanidev/RAG_HRPolicy_ChatBot.git
   cd RAG_HRPolicy_ChatBot
   ```
6. Run deployment:
   ```bash
   ./deploy_azure_native.ps1
   ```

---

## Solution 4: Alternative Deployment via Azure Cloud Shell

This is the **EASIEST** if CLI login doesn't work!

### Step 1: Open Cloud Shell

1. Go to https://portal.azure.com
2. Click **Cloud Shell icon** (>_) at top
3. Select **PowerShell**
4. Wait for terminal to load

✅ **You're automatically logged in!**

### Step 2: Clone Repository

```powershell
# In Cloud Shell
git clone https://github.com/rahulsadhwanidev/RAG_HRPolicy_ChatBot.git
cd RAG_HRPolicy_ChatBot
```

### Step 3: Run Deployment

```powershell
./deploy_azure_native.ps1
```

**Follow the prompts as normal!**

The script will work exactly the same, but you're running it from Azure's own environment.

---

## Solution 5: Hybrid Approach (Portal + CLI)

If only some CLI commands fail:

1. **Create resources in Portal** (Steps above)
2. **Use CLI only for deployment:**

```powershell
# After creating resources manually, just deploy the code
az webapp deployment source config-zip `
  --name hr-chatbot-XXXX `
  --resource-group rg-hr-chatbot `
  --src deploy.zip
```

---

## What's Your Error Message?

### Error: "The command failed with an unexpected error"

**Fix:**
```powershell
# Clear cache
az cache purge

# Clear credentials
az account clear

# Try again
az login
```

---

### Error: "Please run 'az login' to setup account"

**Fix:**
```powershell
# Already running az login, so try device code
az login --use-device-code
```

---

### Error: "Failed to connect to MSI"

**Fix:** You're probably not on an Azure VM, so:
```powershell
az login --use-device-code
```

---

### Error: AADSTS50058 or AADSTS65001

**This means:** Your org requires additional authentication

**Fix:**
1. Talk to your IT admin about Azure access
2. OR use service principal (ask admin for credentials)
3. OR use Azure Cloud Shell (automatically authenticated)

---

## Recommended: Use Azure Cloud Shell

**Why it's better when CLI fails:**
- ✅ Already authenticated (no login needed)
- ✅ All tools pre-installed
- ✅ Works from browser
- ✅ No local security restrictions
- ✅ Access from anywhere

**How to use:**
1. Portal → Cloud Shell icon
2. Select PowerShell
3. Clone repo
4. Run script
5. Done!

---

## Quick Decision Tree

```
Can you login with `az login`?
│
├─ YES → Continue with normal deployment
│
├─ NO → Try `az login --use-device-code`
│   │
│   ├─ Works? → Continue with deployment
│   │
│   └─ Still fails? → Use Azure Cloud Shell
│       OR
│       Create resources manually in Portal
│
└─ Corporate restrictions? → Use Azure Cloud Shell
```

---

## Next Steps

**Choose your path:**

**Path A: Azure Cloud Shell (Recommended)**
1. Open https://portal.azure.com
2. Click Cloud Shell (>_)
3. Run deployment script

**Path B: Manual Portal Setup**
1. Follow steps above to create each resource
2. Deploy code via GitHub or VS Code

**Path C: Fix CLI Login**
1. Try device code: `az login --use-device-code`
2. Contact IT admin if still failing

---

## Need Help?

**Tell me:**
1. What's the exact error message when you run `az login`?
2. Are you on a corporate network?
3. Do you see a browser window open?

And I'll give you specific instructions!

---

## Summary

**If `az login` doesn't work:**

✅ **Best Solution:** Use Azure Cloud Shell
- No installation needed
- Already logged in
- Works from browser
- Same script works!

✅ **Alternative:** Create resources manually in Portal
- More work but very visual
- No CLI needed
- Works 100% of the time

✅ **Quick Fix:** Try device code
```powershell
az login --use-device-code
```

Let me know which approach you want to take!