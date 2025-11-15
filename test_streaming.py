"""
Test script to demonstrate streaming responses from DocuChat API
Usage: python test_streaming.py
"""

import requests
import json
import sys

BASE_URL = "http://localhost:8000"

def test_chat_stream():
    """Test basic chat streaming"""
    print("=" * 60)
    print("Testing Chat Streaming")
    print("=" * 60)
    
    url = f"{BASE_URL}/api/chat/stream"
    payload = {
        "message": "Write a short poem about artificial intelligence"
    }
    
    print(f"\n📤 Sending: {payload['message']}\n")
    print("📥 Streaming response:\n")
    
    try:
        response = requests.post(
            url,
            json=payload,
            headers={"Accept": "text/event-stream"},
            stream=True
        )
        
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                
                # Parse SSE format
                if line_str.startswith('event:'):
                    event_type = line_str.split(':', 1)[1].strip()
                    continue
                elif line_str.startswith('data:'):
                    data_str = line_str.split(':', 1)[1].strip()
                    data = json.loads(data_str)
                    
                    if 'chunk' in data:
                        # Print chunk without newline for streaming effect
                        print(data['chunk'], end='', flush=True)
                    elif 'status' in data:
                        if data['status'] == 'completed':
                            print("\n\n✅ Stream completed!")
                    elif 'error' in data:
                        print(f"\n❌ Error: {data['error']}")
        
        print("\n" + "=" * 60)
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")

def test_rag_stream():
    """Test RAG streaming"""
    print("\n" + "=" * 60)
    print("Testing RAG Streaming")
    print("=" * 60)
    
    url = f"{BASE_URL}/api/rag/ask/stream"
    payload = {
        "question": "What is this document about?"
    }
    
    print(f"\n📤 Asking: {payload['question']}\n")
    
    try:
        response = requests.post(
            url,
            json=payload,
            headers={"Accept": "text/event-stream"},
            stream=True
        )
        
        current_event = None
        
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                
                if line_str.startswith('event:'):
                    current_event = line_str.split(':', 1)[1].strip()
                elif line_str.startswith('data:'):
                    data_str = line_str.split(':', 1)[1].strip()
                    data = json.loads(data_str)
                    
                    if current_event == 'start':
                        print("🔍 Searching documents...\n")
                    
                    elif current_event == 'sources':
                        print("📚 Found sources:")
                        for i, source in enumerate(data['sources'], 1):
                            print(f"  [{i}] {source['filename']} (chunk {source['chunk_index']})")
                            print(f"      Score: {source['score']:.4f}")
                        print("\n💭 Generating answer:\n")
                    
                    elif current_event == 'status':
                        print(f"⏳ {data['message']}\n")
                    
                    elif current_event == 'message':
                        # Stream the answer
                        print(data['chunk'], end='', flush=True)
                    
                    elif current_event == 'done':
                        print("\n\n✅ RAG stream completed!")
                        print(f"   Used {data['num_sources']} source(s)")
                    
                    elif current_event == 'error':
                        print(f"\n❌ Error: {data['error']}")
        
        print("\n" + "=" * 60)
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")

def test_non_stream():
    """Test non-streaming for comparison"""
    print("\n" + "=" * 60)
    print("Testing Non-Streaming (for comparison)")
    print("=" * 60)
    
    url = f"{BASE_URL}/api/chat/"
    payload = {
        "message": "Say hello"
    }
    
    print(f"\n📤 Sending: {payload['message']}")
    print("⏳ Waiting for complete response...\n")
    
    try:
        response = requests.post(url, json=payload)
        data = response.json()
        
        print(f"📥 Response: {data['response']}")
        print("\n✅ Non-streaming completed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")

def main():
    """Run all streaming tests"""
    print("\n🚀 DocuChat Streaming Tests")
    print("=" * 60)
    
    # Check server is running
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=2)
        if response.status_code != 200:
            print("❌ Server is not healthy!")
            sys.exit(1)
        print("✅ Server is healthy\n")
    except Exception as e:
        print(f"❌ Cannot connect to server at {BASE_URL}")
        print(f"   Make sure the server is running: uv run uvicorn app.main:app --reload")
        sys.exit(1)
    
    # Run tests
    try:
        # Test 1: Non-streaming baseline
        test_non_stream()
        
        # Test 2: Chat streaming
        input("\n\nPress Enter to test chat streaming...")
        test_chat_stream()
        
        # Test 3: RAG streaming (if documents are processed)
        print("\n\n📝 Note: RAG streaming requires processed documents.")
        choice = input("Do you have processed documents? (y/n): ").lower()
        if choice == 'y':
            test_rag_stream()
        else:
            print("\nSkipping RAG streaming test.")
            print("To test RAG streaming:")
            print("1. Upload a document: POST /api/upload")
            print("2. Process it: POST /api/rag/process")
            print("3. Run this script again")
        
        print("\n\n✅ All tests completed!")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test failed: {str(e)}")

if __name__ == "__main__":
    main()