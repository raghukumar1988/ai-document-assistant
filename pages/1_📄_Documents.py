"""
Document Management Page
"""

import streamlit as st
import requests
import os

st.set_page_config(
    page_title="Documents - DocuChat",
    page_icon="📄",
    layout="wide"
)

API_BASE_URL = st.secrets.get("API_BASE_URL", "http://localhost:8000")

st.title("📄 Document Management")
st.caption("Upload, process, and manage your documents")

# Get uploaded documents
def get_uploaded_documents():
    try:
        response = requests.get(f"{API_BASE_URL}/api/documents")
        if response.status_code == 200:
            return response.json().get("documents", [])
        return []
    except:
        return []

# Get processed documents
def get_processed_documents():
    try:
        response = requests.get(f"{API_BASE_URL}/api/rag/documents")
        if response.status_code == 200:
            return response.json().get("documents", [])
        return []
    except:
        return []

# Upload and process
col1, col2 = st.columns([2, 1])

with col1:
    st.header("Upload New Document")
    
    uploaded_file = st.file_uploader(
        "Choose a file",
        type=["pdf", "txt", "doc", "docx"],
        help="Supported formats: PDF, TXT, DOC, DOCX"
    )
    
    if uploaded_file:
        col_a, col_b = st.columns(2)
        
        with col_a:
            if st.button("⬆️ Upload", type="primary", use_container_width=True):
                with st.spinner("Uploading..."):
                    try:
                        files = {"file": (uploaded_file.name, uploaded_file, uploaded_file.type)}
                        response = requests.post(f"{API_BASE_URL}/api/upload", files=files)
                        
                        if response.status_code == 200:
                            result = response.json()
                            st.success(f"✅ Uploaded: {result['filename']}")
                            st.json(result)
                        else:
                            st.error("Upload failed")
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
        
        with col_b:
            if st.button("🔄 Upload & Process", type="primary", use_container_width=True):
                with st.spinner("Uploading and processing..."):
                    try:
                        # Upload
                        files = {"file": (uploaded_file.name, uploaded_file, uploaded_file.type)}
                        upload_response = requests.post(f"{API_BASE_URL}/api/upload", files=files)
                        
                        if upload_response.status_code == 200:
                            upload_result = upload_response.json()
                            filename = upload_result['filename']
                            st.success(f"✅ Uploaded: {filename}")
                            
                            # Process
                            process_response = requests.post(
                                f"{API_BASE_URL}/api/rag/process",
                                json={"filename": filename}
                            )
                            
                            if process_response.status_code == 200:
                                process_result = process_response.json()
                                st.success(f"✅ Processed: {process_result['num_chunks']} chunks created")
                                st.json(process_result)
                            else:
                                st.error("Processing failed")
                        else:
                            st.error("Upload failed")
                    except Exception as e:
                        st.error(f"Error: {str(e)}")

with col2:
    st.header("📊 Statistics")
    
    uploaded_docs = get_uploaded_documents()
    processed_docs = get_processed_documents()
    
    st.metric("Uploaded", len(uploaded_docs))
    st.metric("Processed", len(processed_docs))
    
    if uploaded_docs:
        total_size = sum(doc.get("size_bytes", 0) for doc in uploaded_docs)
        st.metric("Total Size", f"{total_size / (1024*1024):.2f} MB")

st.divider()

# Document lists
tab1, tab2 = st.tabs(["📁 Uploaded Documents", "✅ Processed Documents"])

with tab1:
    st.subheader("Uploaded Documents")
    
    uploaded_docs = get_uploaded_documents()
    
    if uploaded_docs:
        for doc in uploaded_docs:
            with st.expander(f"📄 {doc['filename']}"):
                col_a, col_b, col_c = st.columns([2, 1, 1])
                
                with col_a:
                    st.write(f"**Size:** {doc.get('size_mb', 0):.2f} MB")
                    st.write(f"**Type:** {doc.get('extension', 'unknown')}")
                
                with col_b:
                    if st.button("🔄 Process", key=f"process_{doc['filename']}"):
                        with st.spinner("Processing..."):
                            try:
                                response = requests.post(
                                    f"{API_BASE_URL}/api/rag/process",
                                    json={"filename": doc['filename']}
                                )
                                if response.status_code == 200:
                                    result = response.json()
                                    st.success(f"Processed: {result['num_chunks']} chunks")
                                    st.rerun()
                                else:
                                    st.error("Processing failed")
                            except Exception as e:
                                st.error(f"Error: {str(e)}")
                
                with col_c:
                    if st.button("🗑️ Delete", key=f"delete_{doc['filename']}"):
                        try:
                            response = requests.delete(
                                f"{API_BASE_URL}/api/documents/{doc['filename']}"
                            )
                            if response.status_code == 200:
                                st.success("Deleted")
                                st.rerun()
                            else:
                                st.error("Delete failed")
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
    else:
        st.info("No documents uploaded yet")

with tab2:
    st.subheader("Processed Documents (Ready for Search)")
    
    processed_docs = get_processed_documents()
    
    if processed_docs:
        for doc in processed_docs:
            with st.expander(f"✅ {doc}"):
                st.write("This document has been processed and is available for semantic search.")
                
                if st.button("🗑️ Remove from Search", key=f"remove_{doc}"):
                    try:
                        response = requests.delete(
                            f"{API_BASE_URL}/api/rag/documents/{doc}"
                        )
                        if response.status_code == 200:
                            st.success("Removed from search index")
                            st.rerun()
                        else:
                            st.error("Remove failed")
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
    else:
        st.info("No documents processed yet. Upload and process documents to enable search.")