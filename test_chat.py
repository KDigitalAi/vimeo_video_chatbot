import requests
import json

def test_chat(query):
    url = "http://127.0.0.1:8000/chat/query"
    payload = {
        "request": {
            "query": query,
            "user_id": "test_user",
            "include_sources": True
        }
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        result = response.json()
        
        print(f"Query: {query}")
        print(f"Answer: {result.get('answer', 'No answer')}")
        print(f"Sources: {len(result.get('sources', []))} sources found")
        print(f"Processing time: {result.get('processing_time', 0)}s")
        print("-" * 50)
        
        return result
    except Exception as e:
        print(f"Error: {e}")
        return None

# Test queries
test_chat("Hello")
test_chat("What is Python?")
test_chat("Explain variables")