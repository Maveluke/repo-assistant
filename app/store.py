import chromadb

from app.github import DATA_DIR

CHROMA_DIR = DATA_DIR / "chroma"
COLLECTION = "issues"
BATCH_SIZE = 5000

_collection = None


def get_collection():
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        _collection = client.get_or_create_collection(COLLECTION)
    return _collection


def chunk_id(chunk: dict) -> str:
    """Stable, unique id for one chunk."""

    return f"{chunk['repo_whole']}-{chunk['number']}"


def add_chunks(chunks: list[dict]) -> int:
    collection = get_collection()
    for start in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[start : start + BATCH_SIZE]
        collection.upsert(
            ids=[chunk_id(c) for c in batch],
            documents=[c["text"] for c in batch],
            metadatas=[{k: v for k, v in c.items() if k != "text" and v is not None} 
                        for c in batch],
        )
    return len(chunks)


def search(query: str, limit: int = 5) -> list[dict]:
    collection = get_collection()
    response = collection.query(query_texts=[query], n_results=limit)

    # TODO: you write this.
    # Chroma answers many queries at once, so every key is a list of lists -
    # response["documents"] is [[doc, doc, ...]]. You sent one query, so you want
    # index 0 of each. Zip the parallel lists back into one dict per hit, and keep
    # "distances" - it is how you tell a good match from a desperate one.
    return [
        {
            "text": text,
            "distance": dist,
            **meta
        }
        for text, dist, meta in zip(
            response["documents"][0],
            response["distances"][0],
            response["metadatas"][0]
        )
    ]


if __name__ == "__main__":
    from app.chunks import chunk_records, load_records
    owner, repo = "fastapi", "fastapi"

    records = load_records(owner, repo)
    chunks = chunk_records(records, owner, repo)
    print(f"indexing {len(chunks)} chunks...")
    add_chunks(chunks)

    for hit in search("how do I handle authentication with dependencies"):
        print(hit)
