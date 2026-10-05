from langchain_chroma import Chroma
from pathlib import Path

store_path = Path(r"C:\Users\puro755\.vectorstores_graphaide").expanduser()

try:
    chroma = Chroma(persist_directory=str(store_path))
    collections = chroma._client.list_collections()
    print(f"Available collections ({len(collections)} total):")
    for col in collections:
        print(f"  - {col.name}")
        # Count vectors in each
        try:
            count = col._client.count(collection_name=col.name)
            print(f"    Vectors: {count}")
        except:
            try:
                # Try getting all items to count
                items = col.get()
                print(f"    Vectors: {len(items.get('ids', []))}")
            except Exception as e2:
                print(f"    Could not count: {e2}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
