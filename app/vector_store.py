from langchain_openai import AzureOpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from typing import List, Optional, Dict
from pathlib import Path
from app.config import settings
from app.logger import setup_logger
import chromadb

logger = setup_logger("docuchat.vector_store")

class VectorStoreService:
    """Service for managing vector embeddings and semantic search"""
    
    def __init__(self, persist_directory: str = "chroma_db"):
        """
        Initialize vector store service
        
        Args:
            persist_directory: Directory to persist ChromaDB data
        """
        self.persist_directory = persist_directory
        Path(persist_directory).mkdir(exist_ok=True)
        
        # Initialize Azure OpenAI Embeddings
        self.embeddings = AzureOpenAIEmbeddings(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            azure_deployment=settings.azure_openai_embedding_deployment_name,
            api_version=settings.azure_openai_api_version,
        )
        
        # Initialize text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,  # Characters per chunk
            chunk_overlap=200,  # Overlap for context continuity
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        
        # Initialize Chroma client
        self.chroma_client = chromadb.PersistentClient(path=persist_directory)
        
        logger.info(
            "Vector store service initialized",
            extra={
                "persist_directory": persist_directory,
                "chunk_size": 1000,
                "chunk_overlap": 200
            }
        )
    
    def get_collection(self, collection_name: str = "documents") -> Chroma:
        """
        Get or create a Chroma collection
        
        Args:
            collection_name: Name of the collection
            
        Returns:
            Chroma vector store instance
        """
        return Chroma(
            client=self.chroma_client,
            collection_name=collection_name,
            embedding_function=self.embeddings,
        )
    
    def add_document(
        self,
        text: str,
        metadata: dict,
        collection_name: str = "documents"
    ) -> Dict[str, any]:
        """
        Add a document to the vector store
        
        Args:
            text: Document text
            metadata: Document metadata (filename, upload_date, etc.)
            collection_name: Collection to add to
            
        Returns:
            Dictionary with processing statistics
        """
        try:
            logger.info(
                f"Processing document for vector store",
                extra={
                    "uploaded_filename": metadata.get("filename"),
                    "text_length": len(text),
                    "collection": collection_name
                }
            )
            
            # Split text into chunks
            chunks = self.text_splitter.split_text(text)
            
            logger.info(
                f"Document split into {len(chunks)} chunks",
                extra={
                    "uploaded_filename": metadata.get("filename"),
                    "num_chunks": len(chunks),
                    "avg_chunk_size": sum(len(c) for c in chunks) / len(chunks) if chunks else 0
                }
            )
            
            # Create Document objects with metadata
            documents = []
            for i, chunk in enumerate(chunks):
                doc_metadata = metadata.copy()
                doc_metadata["chunk_index"] = i
                doc_metadata["total_chunks"] = len(chunks)
                
                documents.append(
                    Document(
                        page_content=chunk,
                        metadata=doc_metadata
                    )
                )
            
            # Get collection and add documents
            vector_store = self.get_collection(collection_name)
            ids = vector_store.add_documents(documents)
            
            logger.info(
                f"Document added to vector store successfully",
                extra={
                    "uploaded_filename": metadata.get("filename"),
                    "num_chunks": len(chunks),
                    "num_ids": len(ids),
                    "collection": collection_name
                }
            )
            
            return {
                "success": True,
                "num_chunks": len(chunks),
                "chunk_ids": ids,
                "collection": collection_name
            }
            
        except Exception as e:
            logger.error(
                f"Failed to add document to vector store: {str(e)}",
                extra={
                    "uploaded_filename": metadata.get("filename"),
                    "error": str(e)
                },
                exc_info=True
            )
            raise
    
    def search(
        self,
        query: str,
        collection_name: str = "documents",
        k: int = 4,
        filter_metadata: Optional[dict] = None
    ) -> List[Document]:
        """
        Semantic search in vector store
        
        Args:
            query: Search query
            collection_name: Collection to search in
            k: Number of results to return
            filter_metadata: Optional metadata filters
            
        Returns:
            List of relevant Document objects
        """
        try:
            logger.info(
                f"Performing semantic search",
                extra={
                    "query": query[:100],
                    "collection": collection_name,
                    "k": k,
                    "has_filters": bool(filter_metadata)
                }
            )
            
            vector_store = self.get_collection(collection_name)
            
            # Perform similarity search
            if filter_metadata:
                results = vector_store.similarity_search(
                    query,
                    k=k,
                    filter=filter_metadata
                )
            else:
                results = vector_store.similarity_search(query, k=k)
            
            logger.info(
                f"Search completed",
                extra={
                    "query": query[:100],
                    "num_results": len(results),
                    "collection": collection_name
                }
            )
            
            return results
            
        except Exception as e:
            logger.error(
                f"Search failed: {str(e)}",
                extra={
                    "query": query[:100],
                    "collection": collection_name,
                    "error": str(e)
                },
                exc_info=True
            )
            raise
    
    def search_with_scores(
        self,
        query: str,
        collection_name: str = "documents",
        k: int = 4
    ) -> List[tuple]:
        """
        Semantic search with similarity scores
        
        Args:
            query: Search query
            collection_name: Collection to search in
            k: Number of results to return
            
        Returns:
            List of (Document, score) tuples
        """
        try:
            vector_store = self.get_collection(collection_name)
            results = vector_store.similarity_search_with_score(query, k=k)
            
            logger.info(
                f"Search with scores completed",
                extra={
                    "query": query[:100],
                    "num_results": len(results),
                    "best_score": results[0][1] if results else None
                }
            )
            
            return results
            
        except Exception as e:
            logger.error(
                f"Search with scores failed: {str(e)}",
                extra={"query": query[:100]},
                exc_info=True
            )
            raise
    
    def delete_document(
        self,
        filename: str,
        collection_name: str = "documents"
    ) -> bool:
        """
        Delete all chunks of a document from vector store
        
        Args:
            filename: Filename to delete
            collection_name: Collection to delete from
            
        Returns:
            True if successful
        """
        try:
            logger.info(
                f"Deleting document from vector store",
                extra={"filename": filename, "collection": collection_name}
            )
            
            vector_store = self.get_collection(collection_name)
            
            # Delete by metadata filter
            collection = self.chroma_client.get_collection(collection_name)
            collection.delete(where={"filename": filename})
            
            logger.info(
                f"Document deleted from vector store",
                extra={"filename": filename, "collection": collection_name}
            )
            
            return True
            
        except Exception as e:
            logger.error(
                f"Failed to delete document: {str(e)}",
                extra={"filename": filename, "error": str(e)},
                exc_info=True
            )
            raise
    
    def list_documents(self, collection_name: str = "documents") -> List[str]:
        """
        List all unique documents in the collection
        
        Args:
            collection_name: Collection to list from
            
        Returns:
            List of unique filenames
        """
        try:
            collection = self.chroma_client.get_collection(collection_name)
            results = collection.get()
            
            # Extract unique filenames from metadata
            filenames = set()
            if results and results.get('metadatas'):
                for metadata in results['metadatas']:
                    if metadata and 'filename' in metadata:
                        filenames.add(metadata['filename'])
            
            return sorted(list(filenames))
            
        except Exception as e:
            logger.warning(
                f"Failed to list documents: {str(e)}",
                extra={"collection": collection_name}
            )
            return []

# Global vector store service instance
vector_store_service = None

def get_vector_store_service() -> VectorStoreService:
    """Get or create global vector store service instance"""
    global vector_store_service
    if vector_store_service is None:
        vector_store_service = VectorStoreService()
    return vector_store_service