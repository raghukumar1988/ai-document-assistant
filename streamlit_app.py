"""
DocuChat Streamlit UI
Main application file
"""

import streamlit as st
import requests
import json
from typing import List, Dict
import time

# Page configuration
st.set_page_config(
    page_title="DocuChat - AI Document Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# API Configuration
API_BASE_URL = st.secrets.get("API_BASE_URL", "http://localhost:8000")

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        padding: 1rem 0;
    }
    
    .stButton>button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 2rem;
        font-weight: 600;
    }
    
    .stButton>button:hover {
        opacity: 0.9;
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
    }
    
    .document-card {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
        border-left: 4px solid #667eea;
    }
    
    .stat-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 12px;
        text-align: center;
    }
    
    .tool-badge {
        background: #e3f2fd;
        color: #1976d2;
        padding: 0.25rem 0.75rem;
        border-radius: 12px;
        font-size: 0.8rem;
        margin: 0.25rem;
        display: inline-block;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "documents" not in st.session_state:
    st.session_state.documents = []

if "mode" not in st.session_state:
    st.session_state.mode = "chat"

if "pii_protection" not in st.session_state:
    st.session_state.pii_protection = True

# Helper functions
def check_api_health():
    """Check if API is available"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=2)
        return response.status_code == 200
    except:
        return False

def upload_document(file):
    """Upload document to API"""
    try:
        files = {"file": (file.name, file, file.type)}
        response = requests.post(f"{API_BASE_URL}/api/upload", files=files)
        return response.json() if response.status_code == 200 else None
    except Exception as e:
        st.error(f"Upload failed: {str(e)}")
        return None

def process_document(filename):
    """Process document for RAG"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/rag/process",
            json={"filename": filename}
        )
        return response.json() if response.status_code == 200 else None
    except Exception as e:
        st.error(f"Processing failed: {str(e)}")
        return None

def get_documents():
    """Get list of processed documents"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/rag/documents")
        if response.status_code == 200:
            return response.json().get("documents", [])
        return []
    except:
        return []

def send_chat_message(message: str, history: List[Dict] = None):
    """Send chat message"""
    try:
        payload = {"message": message}
        if history:
            payload["chat_history"] = history
        
        response = requests.post(
            f"{API_BASE_URL}/api/chat/",
            json=payload
        )
        
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        st.error(f"Chat failed: {str(e)}")
        return None

def send_agent_message(query: str):
    """Send message to agent"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/agent/run",
            json={"query": query}
        )
        
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        st.error(f"Agent failed: {str(e)}")
        return None

def send_workflow_message(query: str, workflow_type: str = "research"):
    """Send message to workflow"""
    try:
        endpoint = f"{API_BASE_URL}/api/graph/{workflow_type}"
        response = requests.post(endpoint, json={"query": query})
        
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        st.error(f"Workflow failed: {str(e)}")
        return None

def detect_pii(text: str):
    """Detect PII in text"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/guardrails/pii/detect",
            json={"text": text}
        )
        if response.status_code == 200:
            return response.json()
        return None
    except:
        return None

def redact_pii(text: str, mode: str = "mask"):
    """Redact PII from text"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/guardrails/pii/redact",
            json={"text": text, "mode": mode}
        )
        if response.status_code == 200:
            return response.json()
        return None
    except:
        return None

# Main application
def main():
    # Header
    st.markdown('<div class="main-header">🤖 DocuChat</div>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: center; color: #666;">AI-Powered Document Assistant</p>', unsafe_allow_html=True)
    
    # Check API health
    if not check_api_health():
        st.error("⚠️ API server is not responding. Please start the backend server.")
        st.code("uv run uvicorn app.main:app --reload", language="bash")
        return
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Settings")
        
        # Mode selection
        st.session_state.mode = st.selectbox(
            "Mode",
            ["chat", "agent", "research", "rag"],
            format_func=lambda x: {
                "chat": "💬 Chat",
                "agent": "🤖 Agent (Tools)",
                "research": "🔬 Research Workflow",
                "rag": "📚 RAG (Documents)"
            }[x]
        )
        
        # PII Protection
        st.session_state.pii_protection = st.checkbox(
            "🔒 PII Protection",
            value=True,
            help="Detect and mask sensitive information"
        )
        
        st.divider()
        
        # Document Management
        st.header("📄 Documents")
        
        # Upload
        uploaded_file = st.file_uploader(
            "Upload Document",
            type=["pdf", "txt", "doc", "docx"],
            help="Upload a document to analyze"
        )
        
        if uploaded_file:
            with st.spinner("Uploading..."):
                result = upload_document(uploaded_file)
                if result:
                    st.success(f"✅ Uploaded: {result['filename']}")
                    
                    # Auto-process for RAG
                    with st.spinner("Processing for search..."):
                        process_result = process_document(result['filename'])
                        if process_result:
                            st.success(f"✅ Processed: {process_result['num_chunks']} chunks")
                            st.session_state.documents = get_documents()
        
        # List documents
        st.session_state.documents = get_documents()
        
        if st.session_state.documents:
            st.write(f"**{len(st.session_state.documents)} documents processed**")
            for doc in st.session_state.documents[:5]:  # Show first 5
                st.markdown(f'<div class="document-card">📄 {doc}</div>', unsafe_allow_html=True)
            
            if len(st.session_state.documents) > 5:
                st.caption(f"...and {len(st.session_state.documents) - 5} more")
        else:
            st.info("No documents uploaded yet")
        
        st.divider()
        
        # Stats
        st.header("📊 Stats")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Messages", len(st.session_state.messages))
        with col2:
            st.metric("Documents", len(st.session_state.documents))
        
        # Clear chat
        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.messages = []
            st.rerun()
    
    # Main chat area
    st.header(f"{'💬' if st.session_state.mode == 'chat' else '🤖' if st.session_state.mode == 'agent' else '🔬' if st.session_state.mode == 'research' else '📚'} {st.session_state.mode.title()} Mode")
    
    # Display mode description
    mode_descriptions = {
        "chat": "💬 Standard chat with context awareness",
        "agent": "🤖 AI agent with access to tools (calculator, web search, documents)",
        "research": "🔬 Multi-step research workflow with synthesis",
        "rag": "📚 Question answering using your uploaded documents"
    }
    st.caption(mode_descriptions[st.session_state.mode])
    
    # Chat messages container
    chat_container = st.container()
    
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.write(message["content"])
                
                # Show metadata if available
                if "metadata" in message:
                    with st.expander("ℹ️ Details"):
                        if "tools_used" in message["metadata"]:
                            st.write("**Tools Used:**")
                            for tool in message["metadata"]["tools_used"]:
                                st.markdown(f'<span class="tool-badge">{tool}</span>', unsafe_allow_html=True)
                        
                        if "sources" in message["metadata"]:
                            st.write("**Sources:**")
                            for source in message["metadata"]["sources"]:
                                st.caption(f"📄 {source['filename']} (chunk {source['chunk_index']})")
                        
                        if "steps" in message["metadata"]:
                            st.write("**Workflow Steps:**")
                            st.write(" → ".join(message["metadata"]["steps"]))
    
    # Chat input
    if prompt := st.chat_input("Ask me anything..."):
        # Check for PII if protection is enabled
        if st.session_state.pii_protection:
            pii_result = detect_pii(prompt)
            if pii_result and pii_result.get("pii_found"):
                st.warning(f"⚠️ Detected {pii_result['count']} PII entities. Masking sensitive information...")
                redacted = redact_pii(prompt, mode="mask")
                if redacted:
                    prompt = redacted["processed_text"]
        
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message
        with st.chat_message("user"):
            st.write(prompt)
        
        # Get response based on mode
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                if st.session_state.mode == "chat":
                    # Standard chat
                    history = [
                        {"role": m["role"], "content": m["content"]}
                        for m in st.session_state.messages[:-1]
                    ]
                    result = send_chat_message(prompt, history)
                    
                    if result:
                        response = result["response"]
                        metadata = {}
                    else:
                        response = "Sorry, I couldn't process your request."
                        metadata = {}
                
                elif st.session_state.mode == "agent":
                    # Agent mode
                    result = send_agent_message(prompt)
                    
                    if result:
                        response = result["output"]
                        metadata = {"tools_used": [t["tool"] for t in result.get("tool_usage", [])]}
                    else:
                        response = "Sorry, the agent couldn't process your request."
                        metadata = {}
                
                elif st.session_state.mode == "research":
                    # Research workflow
                    result = send_workflow_message(prompt, "research")
                    
                    if result:
                        response = result["result"]["final_answer"] or "Research completed but no answer generated."
                        metadata = {"steps": result.get("steps_executed", [])}
                    else:
                        response = "Sorry, the research workflow failed."
                        metadata = {}
                
                elif st.session_state.mode == "rag":
                    # RAG mode
                    try:
                        rag_response = requests.post(
                            f"{API_BASE_URL}/api/rag/ask",
                            json={"question": prompt}
                        )
                        
                        if rag_response.status_code == 200:
                            result = rag_response.json()
                            response = result["answer"]
                            metadata = {"sources": result.get("sources", [])}
                        else:
                            response = "Sorry, I couldn't find relevant information in your documents."
                            metadata = {}
                    except Exception as e:
                        response = f"RAG query failed: {str(e)}"
                        metadata = {}
                
                # Apply PII protection to response if enabled
                if st.session_state.pii_protection:
                    pii_result = detect_pii(response)
                    if pii_result and pii_result.get("pii_found"):
                        redacted = redact_pii(response, mode="mask")
                        if redacted:
                            response = redacted["processed_text"]
                
                # Display response
                st.write(response)
                
                # Show metadata
                if metadata:
                    with st.expander("ℹ️ Details"):
                        if "tools_used" in metadata and metadata["tools_used"]:
                            st.write("**Tools Used:**")
                            for tool in metadata["tools_used"]:
                                st.markdown(f'<span class="tool-badge">{tool}</span>', unsafe_allow_html=True)
                        
                        if "sources" in metadata and metadata["sources"]:
                            st.write("**Sources:**")
                            for source in metadata["sources"]:
                                st.caption(f"📄 {source['filename']} (chunk {source['chunk_index']})")
                        
                        if "steps" in metadata and metadata["steps"]:
                            st.write("**Workflow Steps:**")
                            st.write(" → ".join(metadata["steps"]))
        
        # Add assistant message
        st.session_state.messages.append({
            "role": "assistant",
            "content": response,
            "metadata": metadata
        })

if __name__ == "__main__":
    main()