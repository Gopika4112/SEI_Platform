
from qdrant_client import QdrantClient, models

client = QdrantClient(host="127.0.0.1", port=6333)

collection_name = "codeatlas_code"

# Delete the old collection if it exists
if client.collection_exists(collection_name):
    client.delete_collection(collection_name)
    print("Deleted old Qdrant collection.")

# Create a new collection for 2048-dimensional embeddings
client.create_collection(
    collection_name=collection_name,
    vectors_config=models.VectorParams(
        size=2048,
        distance=models.Distance.COSINE,
    ),
)

# Verify the actual configuration
info = client.get_collection(collection_name)
print("New collection configuration:", info.config.params.vectors)
print("Qdrant collection reset successfully.")
