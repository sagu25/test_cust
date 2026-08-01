from dotenv import load_dotenv
load_dotenv()
import os
from openai import AzureOpenAI

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
)

deployment = os.getenv("AZURE_EMBEDDING_DEPLOYMENT_NAME")
print("Testing deployment:", deployment)

r = client.embeddings.create(input=["test"], model=deployment)
print("SUCCESS - embedding dim:", len(r.data[0].embedding))
