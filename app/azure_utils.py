# app/azure_utils.py
"""
Azure-specific utilities for Blob Storage integration.
Replaces AWS S3 operations with Azure Blob Storage.
"""

import os
import io
import json
from typing import List, Dict, Any
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from azure.core.exceptions import ResourceNotFoundError

# --- Auto-load .env ---
try:
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv(), override=False)
except Exception:
    pass

# --- Azure Storage Configuration ---
AZURE_STORAGE_ACCOUNT_NAME = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
AZURE_STORAGE_ACCOUNT_KEY = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")
AZURE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_CONTAINER_NAME = os.getenv("AZURE_CONTAINER_NAME", "documents")
AZURE_CHROMADB_CONTAINER = os.getenv("AZURE_CHROMADB_CONTAINER", "chromadb")

# Validate configuration
if not AZURE_CONNECTION_STRING and not (AZURE_STORAGE_ACCOUNT_NAME and AZURE_STORAGE_ACCOUNT_KEY):
    raise RuntimeError(
        "Azure Storage configuration missing. Set either:\n"
        "1. AZURE_STORAGE_CONNECTION_STRING in your .env, OR\n"
        "2. Both AZURE_STORAGE_ACCOUNT_NAME and AZURE_STORAGE_ACCOUNT_KEY"
    )

# --- Initialize Blob Service Client ---
if AZURE_CONNECTION_STRING:
    blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
else:
    account_url = f"https://{AZURE_STORAGE_ACCOUNT_NAME}.blob.core.windows.net"
    blob_service_client = BlobServiceClient(
        account_url=account_url,
        credential=AZURE_STORAGE_ACCOUNT_KEY
    )


def azure_blob_get(blob_name: str, container_name: str = None) -> bytes:
    """
    Download a blob and return its contents as bytes.

    Args:
        blob_name: Name of the blob (e.g., "doc-001/manifest.json")
        container_name: Optional container name (defaults to AZURE_CONTAINER_NAME)

    Returns:
        bytes: Blob contents

    Raises:
        RuntimeError: If blob not found or other error
    """
    container = container_name or AZURE_CONTAINER_NAME

    try:
        blob_client = blob_service_client.get_blob_client(
            container=container,
            blob=blob_name
        )

        # Download blob
        blob_data = blob_client.download_blob()
        return blob_data.readall()

    except ResourceNotFoundError:
        raise RuntimeError(
            f"Blob '{blob_name}' not found in container '{container}'. "
            f"Please ensure the blob exists in your Azure Storage account."
        )
    except Exception as e:
        raise RuntimeError(f"Failed to download blob '{blob_name}': {str(e)}")


def azure_blob_get_json(blob_name: str, container_name: str = None) -> dict:
    """
    Download a JSON blob and return parsed dictionary.

    Args:
        blob_name: Name of the blob (e.g., "doc-001/manifest.json")
        container_name: Optional container name

    Returns:
        dict: Parsed JSON content
    """
    blob_bytes = azure_blob_get(blob_name, container_name)
    return json.loads(blob_bytes.decode("utf-8"))


def azure_blob_upload(blob_name: str, data: bytes, container_name: str = None, overwrite: bool = True) -> str:
    """
    Upload data to a blob.

    Args:
        blob_name: Name of the blob
        data: Bytes to upload
        container_name: Optional container name
        overwrite: Whether to overwrite existing blob

    Returns:
        str: Blob URL
    """
    container = container_name or AZURE_CONTAINER_NAME

    try:
        blob_client = blob_service_client.get_blob_client(
            container=container,
            blob=blob_name
        )

        blob_client.upload_blob(data, overwrite=overwrite)
        return blob_client.url

    except Exception as e:
        raise RuntimeError(f"Failed to upload blob '{blob_name}': {str(e)}")


def azure_blob_upload_json(blob_name: str, data: dict, container_name: str = None, overwrite: bool = True) -> str:
    """
    Upload JSON data to a blob.

    Args:
        blob_name: Name of the blob
        data: Dictionary to upload as JSON
        container_name: Optional container name
        overwrite: Whether to overwrite existing blob

    Returns:
        str: Blob URL
    """
    json_bytes = json.dumps(data, indent=2).encode("utf-8")
    return azure_blob_upload(blob_name, json_bytes, container_name, overwrite)


def azure_blob_list(prefix: str = "", container_name: str = None) -> List[str]:
    """
    List all blobs with a given prefix.

    Args:
        prefix: Blob name prefix (e.g., "doc-001/")
        container_name: Optional container name

    Returns:
        List[str]: List of blob names
    """
    container = container_name or AZURE_CONTAINER_NAME

    try:
        container_client = blob_service_client.get_container_client(container)
        blob_list = container_client.list_blobs(name_starts_with=prefix)
        return [blob.name for blob in blob_list]

    except Exception as e:
        raise RuntimeError(f"Failed to list blobs with prefix '{prefix}': {str(e)}")


def azure_blob_exists(blob_name: str, container_name: str = None) -> bool:
    """
    Check if a blob exists.

    Args:
        blob_name: Name of the blob
        container_name: Optional container name

    Returns:
        bool: True if blob exists, False otherwise
    """
    container = container_name or AZURE_CONTAINER_NAME

    try:
        blob_client = blob_service_client.get_blob_client(
            container=container,
            blob=blob_name
        )
        return blob_client.exists()

    except Exception:
        return False


def azure_blob_delete(blob_name: str, container_name: str = None) -> bool:
    """
    Delete a blob.

    Args:
        blob_name: Name of the blob
        container_name: Optional container name

    Returns:
        bool: True if deleted, False if not found
    """
    container = container_name or AZURE_CONTAINER_NAME

    try:
        blob_client = blob_service_client.get_blob_client(
            container=container,
            blob=blob_name
        )
        blob_client.delete_blob()
        return True

    except ResourceNotFoundError:
        return False
    except Exception as e:
        raise RuntimeError(f"Failed to delete blob '{blob_name}': {str(e)}")


def ensure_containers_exist():
    """
    Ensure required containers exist, create if they don't.
    """
    containers = [AZURE_CONTAINER_NAME, AZURE_CHROMADB_CONTAINER]

    for container in containers:
        try:
            container_client = blob_service_client.get_container_client(container)
            if not container_client.exists():
                container_client.create_container()
                print(f"Created container: {container}")
        except Exception as e:
            print(f"Warning: Could not verify/create container '{container}': {e}")


# Initialize containers on module import
try:
    ensure_containers_exist()
except Exception as e:
    print(f"Warning: Container initialization failed: {e}")


# --- Backward compatibility aliases for drop-in replacement ---
def blob_get(key: str) -> bytes:
    """Alias for azure_blob_get for backward compatibility."""
    return azure_blob_get(key)


def blob_get_json(key: str) -> dict:
    """Alias for azure_blob_get_json for backward compatibility."""
    return azure_blob_get_json(key)