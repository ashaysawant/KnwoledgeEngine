import requests
import weaviate
import os
from weaviate.classes.init import Auth
from weaviate.collections import Collection
from weaviate.collections.classes.config import Configure
from docx import Document
from pypdf import PdfReader

# Replace these with your app credentials
TENANT_ID = os.environ.get("SHAREPOINT_TENANT_ID")
CLIENT_ID = os.environ.get("SHAREPOINT_CLIENT_ID")
CLIENT_SECRET = os.environ.get("SHAREPOINT_CLIENT_SECRET")
SHAREPOINT_SITE_URL = "https://ashaysawant.sharepoint.com/sites/Credit"
DOCUMENT_LIBRARY_NAME = "Shared Documents"


# Microsoft Identity Platform token endpoint
TOKEN_URL = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"

# Weaviate credentials
WEAVIATE_CLOUD_URL = os.environ.get("WEAVIATE_CLOUD_URL")
WEAVIATE_API_KEY = os.environ.get("WEAVIATE_API_KEY")
COHERE_API_KEY = os.environ.get("COHERE_API_KEY")

# Initialize Weaviate client securely
client = weaviate.connect_to_weaviate_cloud(
    cluster_url=WEAVIATE_CLOUD_URL,
    auth_credentials=Auth.api_key(WEAVIATE_API_KEY),
    headers={"X-Cohere-Api-Key": COHERE_API_KEY}
)

# Check if the client is ready
print(client.is_ready())

# Create a collection if it doesn't exist
if client.collections.exists("Document"):
    print("Collection 'Document' already exists.")
else:
    # Create the collection
    document_collection = client.collections.create(
        name="Document",
        vectorizer_config=Configure.Vectorizer.text2vec_cohere(),  # Use Cohere for vector embeddings
        generative_config=Configure.Generative.cohere(),  # Use Cohere for generative AI
    )
    print(f"Collection created: {document_collection.name}")

# Request an access token
def get_access_token(client_id, client_secret, tenant_id):
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "https://graph.microsoft.com/.default"
    }
    response = requests.post(TOKEN_URL, headers=headers, data=data)
    response.raise_for_status()
    return response.json()["access_token"]

# Get the site ID
def get_site_id(access_token, site_url):
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    formatted_site_url = site_url.replace("https://", "").replace("/sites/", ":/sites/")
    graph_url = f"https://graph.microsoft.com/v1.0/sites/{formatted_site_url}"
    response = requests.get(graph_url, headers=headers)
    response.raise_for_status()
    return response.json()["id"]

# Get files from a document library
def get_files(access_token, site_id, document_library_name):
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    # Fetch the drive ID for the document library
    graph_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives?$filter=name eq '{document_library_name}'"
    response = requests.get(graph_url, headers=headers)
    response.raise_for_status()
    drive_id = response.json()["value"][0]["id"]

    # Get files in the drive
    graph_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives/{drive_id}/root/children"
    response = requests.get(graph_url, headers=headers)
    response.raise_for_status()
    files = response.json()["value"]

    return drive_id, files

# Download a file
def download_file(access_token, site_id, drive_id, file_id, file_name):
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    # Correct URL format for downloading a file
    graph_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives/{drive_id}/items/{file_id}/content"
    response = requests.get(graph_url, headers=headers)
    response.raise_for_status()

    # Save the file locally
    with open(file_name, "wb") as f:
        f.write(response.content)
    print(f"File downloaded: {file_name}")

# Extract text from a .txt file
def extract_text_from_txt(file_name):
    with open(file_name, "r") as f:
        return f.read()

# Extract text from a .docx file
def extract_text_from_docx(file_name):
    doc = Document(file_name)
    text = "\n".join([para.text for para in doc.paragraphs])
    return text

# Extract text from a .pdf file
def extract_text_from_pdf(file_name):
    reader = PdfReader(file_name)
    text = "\n".join([page.extract_text() for page in reader.pages])
    return text

# Add data to Weaviate using batch insertion
def add_to_weaviate(file_name, content):
    with client.collections.get("Document").batch.dynamic() as batch:
        batch.add_object({
            "fileName": file_name,
            "content": content
        })
    print(f"Data added to Weaviate for file: {file_name}")

# Main script
if __name__ == "__main__":
    # Get the access token
    access_token = get_access_token(CLIENT_ID, CLIENT_SECRET, TENANT_ID)
    print("Access token retrieved successfully!")

    # Get the site ID
    site_id = get_site_id(access_token, SHAREPOINT_SITE_URL)
    print(f"Site ID: {site_id}")

    # Get the drive ID and files from the document library
    drive_id, files = get_files(access_token, site_id, DOCUMENT_LIBRARY_NAME)
    print("Files in the document library:")
    for file in files:
        file_name = file["name"]
        file_id = file["id"]
        print(f"File Name: {file_name}, File ID: {file_id}")

        # Download the file
        download_file(access_token, site_id, drive_id, file_id, file_name)

        # Extract text based on file type
        if file_name.endswith(".txt"):
            content = extract_text_from_txt(file_name)
        elif file_name.endswith(".docx"):
            content = extract_text_from_docx(file_name)
        elif file_name.endswith(".pdf"):
            content = extract_text_from_pdf(file_name)
        else:
            print(f"Unsupported file type: {file_name}")
            continue

        # Add the extracted content to Weaviate
        add_to_weaviate(file_name, content)

    # Close the Weaviate client

    client.close()