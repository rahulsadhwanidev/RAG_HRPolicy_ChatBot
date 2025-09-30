# Azure Migration Guide - HR Policy Chatbot

## Table of Contents
1. [Migration Overview](#migration-overview)
2. [Azure Service Mappings](#azure-service-mappings)
3. [Prerequisites](#prerequisites)
4. [Code Changes Required](#code-changes-required)
5. [Azure Infrastructure Setup](#azure-infrastructure-setup)
6. [Deployment Strategies](#deployment-strategies)
7. [Configuration Changes](#configuration-changes)
8. [Testing & Validation](#testing--validation)
9. [Cost Optimization](#cost-optimization)
10. [Monitoring & Observability](#monitoring--observability)

---

## Migration Overview

### Current AWS Architecture
- **Storage**: AWS S3 for PDF documents and manifest.json
- **SDK**: boto3 for S3 operations
- **Hosting**: Can be deployed on AWS ECS/Fargate
- **Authentication**: AWS IAM roles and policies

### Target Azure Architecture
- **Storage**: Azure Blob Storage for PDF documents and manifest.json
- **SDK**: azure-storage-blob for blob operations
- **Hosting**: Azure Container Instances (ACI) or Azure App Service
- **Authentication**: Azure Managed Identity or Service Principal

### Migration Benefits
- **Cost Optimization**: Azure's competitive pricing for storage and compute
- **Integration**: Better integration with existing Azure enterprise services
- **Compliance**: Azure's comprehensive compliance certifications
- **Hybrid Support**: Seamless hybrid cloud capabilities

---

## Azure Service Mappings

| Current AWS Service | Azure Equivalent | Purpose | Migration Complexity |
|-------------------|-----------------|---------|---------------------|
| **S3 Bucket** | **Azure Blob Storage** | Document storage | Medium |
| **IAM Roles** | **Managed Identity** | Authentication | Low |
| **CloudWatch** | **Azure Monitor** | Logging & metrics | Low |
| **ECS/Fargate** | **Container Instances** | Container hosting | Medium |
| **Secrets Manager** | **Key Vault** | Secret management | Low |
| **VPC** | **Virtual Network** | Network isolation | Low |

### Service Comparison Details

#### Storage Layer
```
AWS S3                          →    Azure Blob Storage
├── Buckets                     →    ├── Storage Accounts
├── Objects (PDFs)              →    ├── Blobs (PDFs)
├── Folders (doc-001/)          →    ├── Containers (doc-001)
├── Lifecycle policies          →    ├── Lifecycle management
└── Versioning                  →    └── Blob versioning
```

#### Authentication
```
AWS IAM                         →    Azure Identity
├── IAM Roles                   →    ├── Managed Identity
├── IAM Policies                →    ├── RBAC Roles
├── Access Keys                 →    ├── Service Principal
└── Resource-based policies     →    └── Resource permissions
```

---

## Prerequisites

### Azure Account Setup
1. **Azure Subscription**: Active Azure subscription with appropriate permissions
2. **Resource Group**: Create a dedicated resource group for the chatbot
3. **Storage Account**: Create Azure Storage Account with Blob service enabled
4. **Identity Management**: Set up Managed Identity or Service Principal

### Required Azure CLI Tools
```bash
# Install Azure CLI
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Login to Azure
az login

# Set default subscription
az account set --subscription "your-subscription-id"
```

### Python SDK Requirements
```bash
# Remove AWS dependencies
pip uninstall boto3 botocore

# Install Azure dependencies
pip install azure-storage-blob azure-identity python-dotenv
```

---

## Code Changes Required

### 1. Dependencies Update

**Current requirements.txt:**
```txt
boto3                # AWS SDK - REMOVE
```

**New requirements.txt:**
```txt
azure-storage-blob   # Azure Blob Storage SDK
azure-identity       # Azure authentication
```

### 2. Environment Variables

**Current .env (AWS):**
```bash
AWS_REGION=us-east-1
S3_BUCKET=ragbot-rahul-20250914183649
# AWS credentials handled by IAM roles
```

**New .env (Azure):**
```bash
AZURE_STORAGE_ACCOUNT=hrpolicystorage
AZURE_CONTAINER_NAME=hr-documents
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...
# Or use Managed Identity (recommended)
```

### 3. Core Code Changes

#### A. Create Azure Storage Utility (`app/azure_utils.py`)

```python
# app/azure_utils.py
import os
import json
from typing import Optional
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
import logging

logger = logging.getLogger(__name__)

class AzureStorageManager:
    def __init__(self):
        """Initialize Azure Blob Storage client with Managed Identity or connection string"""
        self.storage_account = os.getenv("AZURE_STORAGE_ACCOUNT")
        self.container_name = os.getenv("AZURE_CONTAINER_NAME", "hr-documents")

        # Try Managed Identity first (recommended for production)
        try:
            credential = DefaultAzureCredential()
            account_url = f"https://{self.storage_account}.blob.core.windows.net"
            self.blob_service_client = BlobServiceClient(
                account_url=account_url,
                credential=credential
            )
            logger.info("Using Azure Managed Identity for authentication")
        except Exception as e:
            # Fallback to connection string (for development)
            connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
            if not connection_string:
                raise RuntimeError(
                    "Azure authentication failed. Set either AZURE_STORAGE_ACCOUNT with "
                    "Managed Identity or AZURE_STORAGE_CONNECTION_STRING"
                )
            self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
            logger.info("Using Azure connection string for authentication")

        self.container_client = self.blob_service_client.get_container_client(self.container_name)

    def get_blob(self, blob_name: str) -> bytes:
        """Download blob content as bytes (equivalent to s3_get)"""
        try:
            blob_client = self.container_client.get_blob_client(blob_name)
            download_stream = blob_client.download_blob()
            return download_stream.readall()
        except Exception as e:
            logger.error(f"Failed to download blob {blob_name}: {e}")
            raise

    def get_blob_json(self, blob_name: str) -> dict:
        """Download JSON blob and parse (equivalent to s3_get_json)"""
        try:
            blob_bytes = self.get_blob(blob_name)
            return json.loads(blob_bytes.decode('utf-8'))
        except Exception as e:
            logger.error(f"Failed to download JSON blob {blob_name}: {e}")
            raise

    def upload_blob(self, blob_name: str, data: bytes, overwrite: bool = True):
        """Upload blob data"""
        try:
            blob_client = self.container_client.get_blob_client(blob_name)
            blob_client.upload_blob(data, overwrite=overwrite)
            logger.info(f"Successfully uploaded blob: {blob_name}")
        except Exception as e:
            logger.error(f"Failed to upload blob {blob_name}: {e}")
            raise

    def list_blobs(self, prefix: str = "") -> list:
        """List blobs with optional prefix filter"""
        try:
            blob_list = []
            for blob in self.container_client.list_blobs(name_starts_with=prefix):
                blob_list.append({
                    'name': blob.name,
                    'size': blob.size,
                    'last_modified': blob.last_modified
                })
            return blob_list
        except Exception as e:
            logger.error(f"Failed to list blobs with prefix {prefix}: {e}")
            raise

# Global instance
azure_storage = AzureStorageManager()

# Compatibility functions (drop-in replacements)
def azure_get(blob_name: str) -> bytes:
    """Azure equivalent of s3_get"""
    return azure_storage.get_blob(blob_name)

def azure_get_json(blob_name: str) -> dict:
    """Azure equivalent of s3_get_json"""
    return azure_storage.get_blob_json(blob_name)
```

#### B. Update `app/utils.py`

**Replace AWS imports:**
```python
# OLD (AWS)
import boto3
s3 = boto3.client("s3", region_name=AWS_REGION)

# NEW (Azure)
from .azure_utils import azure_get, azure_get_json
```

**Update function calls:**
```python
# OLD (AWS)
def ensure_ingested() -> Dict[str, Any]:
    manifest = s3_get_json(manifest_key)
    pdf_bytes = s3_get(latest_key)

# NEW (Azure)
def ensure_ingested() -> Dict[str, Any]:
    manifest = azure_get_json(manifest_key)
    pdf_bytes = azure_get(latest_key)
```

#### C. Update `app/main.py`

**Replace imports:**
```python
# OLD
from .utils import (
    s3_get,
    s3_get_json,
)

# NEW
from .utils import (
    azure_get,
    azure_get_json,
)
```

### 4. Complete Updated Files

#### Updated `app/utils.py` (Azure version)
```python
# app/utils.py
import os, io, time, json
from typing import List
from pypdf import PdfReader
import tiktoken
from openai import OpenAI
from .azure_utils import azure_get, azure_get_json

# --- Auto-load .env ---
try:
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv(), override=False)
except Exception:
    pass

# --- Config from env ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError(
        "OPENAI_API_KEY is not set. Add it to your .env as OPENAI_API_KEY=sk-... "
    )

CHAT_MODEL   = os.getenv("CHAT_MODEL", "gpt-4o-mini")
EMBED_MODEL  = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

# --- SDK clients ---
client = OpenAI(api_key=OPENAI_API_KEY)

# --- Tokenizer (for chunking) ---
ENC = tiktoken.get_encoding("cl100k_base")

# ... [rest of the file remains the same, just replace s3_get/s3_get_json calls with azure_get/azure_get_json]
```

---

## Azure Infrastructure Setup

### 1. Create Resource Group
```bash
# Create resource group
az group create \
    --name "rg-hr-chatbot" \
    --location "East US"
```

### 2. Create Storage Account
```bash
# Create storage account
az storage account create \
    --name "hrpolicystorage" \
    --resource-group "rg-hr-chatbot" \
    --location "East US" \
    --sku "Standard_LRS" \
    --kind "StorageV2" \
    --access-tier "Hot"

# Create container for documents
az storage container create \
    --name "hr-documents" \
    --account-name "hrpolicystorage" \
    --public-access "off"
```

### 3. Set up Managed Identity
```bash
# Create user-assigned managed identity
az identity create \
    --name "hr-chatbot-identity" \
    --resource-group "rg-hr-chatbot"

# Get identity details
az identity show \
    --name "hr-chatbot-identity" \
    --resource-group "rg-hr-chatbot" \
    --query '{clientId:clientId, principalId:principalId, resourceId:id}' \
    --output table
```

### 4. Assign Storage Permissions
```bash
# Assign Storage Blob Data Contributor role
az role assignment create \
    --assignee "PRINCIPAL_ID_FROM_ABOVE" \
    --role "Storage Blob Data Contributor" \
    --scope "/subscriptions/YOUR_SUBSCRIPTION_ID/resourceGroups/rg-hr-chatbot/providers/Microsoft.Storage/storageAccounts/hrpolicystorage"
```

### 5. Create Key Vault (for secrets)
```bash
# Create Key Vault
az keyvault create \
    --name "hr-chatbot-kv" \
    --resource-group "rg-hr-chatbot" \
    --location "East US"

# Store OpenAI API key
az keyvault secret set \
    --vault-name "hr-chatbot-kv" \
    --name "openai-api-key" \
    --value "your-openai-api-key"

# Grant access to managed identity
az keyvault set-policy \
    --name "hr-chatbot-kv" \
    --object-id "PRINCIPAL_ID_FROM_ABOVE" \
    --secret-permissions get list
```

---

## Deployment Strategies

### Option 1: Azure Container Instances (Recommended)

#### Dockerfile (Azure-optimized)
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directories
RUN mkdir -p /app/data/chroma /app/.state

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### Deploy to Azure Container Instances
```bash
# Build and push to Azure Container Registry
az acr create \
    --name "hrpolicyacr" \
    --resource-group "rg-hr-chatbot" \
    --sku "Basic"

# Login to ACR
az acr login --name "hrpolicyacr"

# Build and push image
docker build -t hrpolicyacr.azurecr.io/hr-chatbot:latest .
docker push hrpolicyacr.azurecr.io/hr-chatbot:latest

# Deploy to Container Instances
az container create \
    --resource-group "rg-hr-chatbot" \
    --name "hr-chatbot-instance" \
    --image "hrpolicyacr.azurecr.io/hr-chatbot:latest" \
    --assign-identity "hr-chatbot-identity" \
    --environment-variables \
        AZURE_STORAGE_ACCOUNT=hrpolicystorage \
        AZURE_CONTAINER_NAME=hr-documents \
        DOC_ID=doc-001 \
        THRESHOLD=0.3 \
        TOP_K=6 \
    --secure-environment-variables \
        OPENAI_API_KEY=your-openai-key \
    --dns-name-label "hr-policy-chatbot" \
    --ports 8000 \
    --memory 2 \
    --cpu 1
```

### Option 2: Azure App Service

#### Deploy to App Service
```bash
# Create App Service Plan
az appservice plan create \
    --name "hr-chatbot-plan" \
    --resource-group "rg-hr-chatbot" \
    --sku "B1" \
    --is-linux

# Create Web App
az webapp create \
    --name "hr-policy-chatbot" \
    --resource-group "rg-hr-chatbot" \
    --plan "hr-chatbot-plan" \
    --deployment-container-image-name "hrpolicyacr.azurecr.io/hr-chatbot:latest"

# Configure managed identity
az webapp identity assign \
    --name "hr-policy-chatbot" \
    --resource-group "rg-hr-chatbot" \
    --identities "hr-chatbot-identity"

# Configure app settings
az webapp config appsettings set \
    --name "hr-policy-chatbot" \
    --resource-group "rg-hr-chatbot" \
    --settings \
        AZURE_STORAGE_ACCOUNT=hrpolicystorage \
        AZURE_CONTAINER_NAME=hr-documents \
        DOC_ID=doc-001 \
        THRESHOLD=0.3 \
        TOP_K=6 \
        OPENAI_API_KEY=@Microsoft.KeyVault\(SecretUri=https://hr-chatbot-kv.vault.azure.net/secrets/openai-api-key/\)
```

### Option 3: Azure Kubernetes Service (AKS)

#### Kubernetes Deployment
```yaml
# k8s-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hr-chatbot
  namespace: default
spec:
  replicas: 2
  selector:
    matchLabels:
      app: hr-chatbot
  template:
    metadata:
      labels:
        app: hr-chatbot
        azure.workload.identity/use: "true"
    spec:
      serviceAccountName: hr-chatbot-sa
      containers:
      - name: hr-chatbot
        image: hrpolicyacr.azurecr.io/hr-chatbot:latest
        ports:
        - containerPort: 8000
        env:
        - name: AZURE_STORAGE_ACCOUNT
          value: "hrpolicystorage"
        - name: AZURE_CONTAINER_NAME
          value: "hr-documents"
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: openai-secret
              key: api-key
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: hr-chatbot-service
spec:
  selector:
    app: hr-chatbot
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

---

## Configuration Changes

### 1. Azure Environment Variables

**Production .env (Azure):**
```bash
# Azure Storage Configuration
AZURE_STORAGE_ACCOUNT=hrpolicystorage
AZURE_CONTAINER_NAME=hr-documents

# Application Configuration
DOC_ID=doc-001
THRESHOLD=0.3
TOP_K=6

# OpenAI Configuration
CHAT_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small

# Azure Key Vault (if using)
AZURE_KEY_VAULT_NAME=hr-chatbot-kv

# Managed Identity Client ID (if using user-assigned)
AZURE_CLIENT_ID=your-managed-identity-client-id
```

### 2. Document Structure Migration

#### Current AWS Structure:
```
s3://ragbot-rahul-20250914183649/
├── doc-001/
│   ├── manifest.json
│   └── 1757900901.pdf
```

#### New Azure Structure:
```
hrpolicystorage/hr-documents/
├── doc-001/
│   ├── manifest.json
│   └── 1757900901.pdf
```

#### Migration Script:
```python
# migrate_s3_to_azure.py
import boto3
from azure.storage.blob import BlobServiceClient
import os

def migrate_documents():
    # AWS S3 client
    s3 = boto3.client('s3')
    s3_bucket = "ragbot-rahul-20250914183649"

    # Azure Blob client
    azure_conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    blob_service = BlobServiceClient.from_connection_string(azure_conn_str)
    container_name = "hr-documents"

    # List all objects in S3
    response = s3.list_objects_v2(Bucket=s3_bucket)

    for obj in response.get('Contents', []):
        key = obj['Key']
        print(f"Migrating: {key}")

        # Download from S3
        s3_response = s3.get_object(Bucket=s3_bucket, Key=key)
        data = s3_response['Body'].read()

        # Upload to Azure
        blob_client = blob_service.get_blob_client(
            container=container_name,
            blob=key
        )
        blob_client.upload_blob(data, overwrite=True)
        print(f"✓ Migrated: {key}")

if __name__ == "__main__":
    migrate_documents()
    print("Migration completed!")
```

---

## Testing & Validation

### 1. Local Testing with Azure

```bash
# Set up local environment
export AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=..."
export AZURE_CONTAINER_NAME="hr-documents"
export DOC_ID="doc-001"
export OPENAI_API_KEY="your-key"

# Run locally
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Testing Checklist

- [ ] **Authentication**: Managed Identity works correctly
- [ ] **Document Access**: Can download PDFs from Azure Blob Storage
- [ ] **Manifest Reading**: JSON manifest parsing works
- [ ] **Vector Search**: ChromaDB integration unchanged
- [ ] **API Endpoints**: All endpoints respond correctly
- [ ] **UI Interface**: Frontend works with new backend
- [ ] **Session Management**: Conversation state preserved
- [ ] **Cost Tracking**: OpenAI usage tracking works

### 3. Performance Benchmarks

```python
# test_azure_performance.py
import time
from app.azure_utils import azure_get, azure_get_json

def benchmark_azure_storage():
    start_time = time.time()

    # Test manifest download
    manifest = azure_get_json("doc-001/manifest.json")
    manifest_time = time.time() - start_time

    # Test PDF download
    pdf_start = time.time()
    pdf_bytes = azure_get("doc-001/1757900901.pdf")
    pdf_time = time.time() - pdf_start

    print(f"Manifest download: {manifest_time:.2f}s")
    print(f"PDF download: {pdf_time:.2f}s")
    print(f"PDF size: {len(pdf_bytes)} bytes")

if __name__ == "__main__":
    benchmark_azure_storage()
```

---

## Cost Optimization

### 1. Azure Storage Costs

| Component | AWS S3 | Azure Blob | Monthly Cost (1GB) |
|-----------|--------|------------|-------------------|
| **Standard Storage** | $0.023/GB | $0.0184/GB | ~$0.02 |
| **Requests (1000)** | $0.0004 | $0.0004 | ~$0.40 |
| **Data Transfer** | $0.09/GB | $0.087/GB | Variable |

**Optimization Strategies:**
- Use **Cool Access Tier** for infrequently accessed documents
- Enable **Lifecycle Management** for automatic tier transitions
- Implement **Content Compression** for large PDFs

### 2. Compute Costs

| Service | Configuration | Monthly Cost |
|---------|--------------|--------------|
| **Container Instances** | 1 vCPU, 2GB RAM | ~$30 |
| **App Service B1** | 1 Core, 1.75GB RAM | ~$13 |
| **AKS Standard** | 2 nodes, Standard_B2s | ~$60 |

### 3. Cost Monitoring

```bash
# Set up cost alerts
az consumption budget create \
    --budget-name "hr-chatbot-budget" \
    --amount 100 \
    --time-grain "Monthly" \
    --time-period start-date="2025-01-01" \
    --resource-group "rg-hr-chatbot"
```

---

## Monitoring & Observability

### 1. Azure Monitor Integration

```python
# Add to app/main.py
import logging
from opencensus.ext.azure.log_exporter import AzureLogHandler

# Configure Azure Monitor logging
logger = logging.getLogger(__name__)
logger.addHandler(AzureLogHandler(
    connection_string=os.getenv('APPLICATIONINSIGHTS_CONNECTION_STRING')
))

# Custom metrics
from opencensus.ext.azure import metrics_exporter
from opencensus.stats import aggregation as aggregation_module
from opencensus.stats import measure as measure_module
from opencensus.stats import stats as stats_module
from opencensus.stats import view as view_module
from opencensus.tags import tag_map as tag_map_module

# Create metrics
query_measure = measure_module.MeasureInt("queries_total", "Total queries processed")
latency_measure = measure_module.MeasureFloat("query_latency", "Query latency in ms")

# Track metrics in /ask endpoint
@app.post("/ask")
def ask(body: AskBody):
    # ... existing code ...

    # Log to Azure Monitor
    logger.info(f"Query processed: {body.question[:50]}...", extra={
        'custom_dimensions': {
            'session_id': session_id,
            'latency_ms': total_time,
            'sources_found': len(set(pages)),
            'tokens_used': ptok + ctok
        }
    })

    # Record metrics
    mmap = stats.stats.stats_recorder.new_measurement_map()
    mmap.measure_int_put(query_measure, 1)
    mmap.measure_float_put(latency_measure, total_time)
    mmap.record()
```

### 2. Application Insights Dashboard

```json
{
    "name": "HR Chatbot Dashboard",
    "tiles": [
        {
            "title": "Query Volume",
            "type": "timeseries",
            "query": "customMetrics | where name == 'queries_total' | summarize sum(value) by bin(timestamp, 1h)"
        },
        {
            "title": "Average Latency",
            "type": "timeseries",
            "query": "customMetrics | where name == 'query_latency' | summarize avg(value) by bin(timestamp, 1h)"
        },
        {
            "title": "Error Rate",
            "type": "scalar",
            "query": "traces | where severityLevel >= 3 | summarize count() by bin(timestamp, 1h)"
        }
    ]
}
```

### 3. Health Monitoring

```python
# Enhanced health check for Azure
@app.get("/health")
def health():
    state = read_state()
    health_status = {
        "status": "healthy",
        "doc_id": DOC_ID,
        "last_ingested_key": state.get("last_ingested_key"),
        "pages": state.get("pages"),
        "chunks": state.get("chunks"),
        "azure_storage": "unknown",
        "openai_api": "unknown"
    }

    try:
        # Test Azure Storage connectivity
        from .azure_utils import azure_storage
        azure_storage.container_client.get_container_properties()
        health_status["azure_storage"] = "healthy"
    except Exception as e:
        health_status["azure_storage"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"

    try:
        # Test OpenAI API connectivity
        from .utils import client
        client.models.list()
        health_status["openai_api"] = "healthy"
    except Exception as e:
        health_status["openai_api"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"

    return health_status
```

---

## Summary

This migration guide provides a comprehensive path to move your HR Policy Chatbot from AWS to Azure. The key changes involve:

1. **Storage**: Replace S3 with Azure Blob Storage
2. **Authentication**: Use Azure Managed Identity instead of IAM roles
3. **SDK**: Switch from boto3 to azure-storage-blob
4. **Deployment**: Leverage Azure Container Instances or App Service
5. **Monitoring**: Integrate with Azure Monitor and Application Insights

The migration maintains all existing functionality while providing Azure-native integrations and potentially better cost optimization for your enterprise environment.

**Next Steps:**
1. Set up Azure infrastructure using the provided scripts
2. Implement code changes in a development environment
3. Test thoroughly with your actual HR documents
4. Perform gradual migration of production workload
5. Set up monitoring and alerting in Azure Monitor

**Estimated Migration Time:** 2-3 days for a skilled developer, including testing and validation.