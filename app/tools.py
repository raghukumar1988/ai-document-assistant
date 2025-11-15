from langchain_core.tools import Tool
from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
# from langchain.agents import load_tools
from app.vector_store import get_vector_store_service
from app.logger import setup_logger
import numexpr

logger = setup_logger("docuchat.tools")

def create_calculator_tool():
    """Create a calculator tool for mathematical operations"""
    
    def calculator(expression: str) -> str:
        """
        Perform mathematical calculations.
        
        Args:
            expression: Mathematical expression to evaluate (e.g., "2 + 2", "sqrt(16)")
            
        Returns:
            Result of the calculation
        """
        try:
            logger.info(f"Calculator tool called with expression: {expression}")
            result = numexpr.evaluate(expression).item()
            logger.info(f"Calculator result: {result}")
            return str(result)
        except Exception as e:
            error_msg = f"Error calculating '{expression}': {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    return Tool(
        name="Calculator",
        func=calculator,
        description=(
            "Useful for performing mathematical calculations. "
            "Input should be a mathematical expression like '2 + 2' or 'sqrt(16)'. "
            "Supports basic operations (+, -, *, /), power (**), sqrt, and more."
        )
    )

def create_web_search_tool():
    """Create a web search tool using DuckDuckGo"""
    
    search = DuckDuckGoSearchAPIWrapper(max_results=3)
    
    def web_search(query: str) -> str:
        """
        Search the web for current information.
        
        Args:
            query: Search query
            
        Returns:
            Search results as formatted string
        """
        try:
            logger.info(f"Web search tool called with query: {query}")
            results = search.run(query)
            logger.info(f"Web search returned results")
            return results
        except Exception as e:
            error_msg = f"Error searching for '{query}': {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg
    
    return Tool(
        name="WebSearch",
        func=web_search,
        description=(
            "Useful for finding current information on the internet. "
            "Input should be a search query. "
            "Use this when you need up-to-date information or facts not in your knowledge."
        )
    )

def create_document_search_tool():
    """Create a tool to search uploaded documents"""
    
    def document_search(query: str) -> str:
        """
        Search through uploaded documents using semantic search.
        
        Args:
            query: Search query about the documents
            
        Returns:
            Relevant document excerpts
        """
        try:
            logger.info(f"Document search tool called with query: {query}")
            
            vector_store = get_vector_store_service()
            results = vector_store.search(query, k=3)
            
            if not results:
                return "No relevant documents found. Ask the user to upload and process documents first."
            
            # Format results
            formatted_results = []
            for i, doc in enumerate(results, 1):
                formatted_results.append(
                    f"[Source {i}: {doc.metadata.get('filename', 'Unknown')}]\n"
                    f"{doc.page_content[:500]}..."
                )
            
            logger.info(f"Document search found {len(results)} results")
            return "\n\n".join(formatted_results)
            
        except Exception as e:
            error_msg = f"Error searching documents: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg
    
    return Tool(
        name="DocumentSearch",
        func=document_search,
        description=(
            "Search through the user's uploaded documents. "
            "Use this when the user asks questions about their documents. "
            "Input should be a search query about the document content."
        )
    )

def create_document_list_tool():
    """Create a tool to list available documents"""
    
    def list_documents(query: str = "") -> str:
        """
        List all processed documents available for search.
        
        Args:
            query: Not used, can be empty
            
        Returns:
            List of document filenames
        """
        try:
            logger.info("Document list tool called")
            
            vector_store = get_vector_store_service()
            documents = vector_store.list_documents()
            
            if not documents:
                return "No documents have been processed yet. The user needs to upload and process documents first."
            
            doc_list = "\n".join([f"- {doc}" for doc in documents])
            logger.info(f"Found {len(documents)} processed documents")
            return f"Available documents:\n{doc_list}"
            
        except Exception as e:
            error_msg = f"Error listing documents: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg
    
    return Tool(
        name="ListDocuments",
        func=list_documents,
        description=(
            "List all documents that have been uploaded and processed. "
            "Use this to check what documents are available before searching them. "
            "No input needed."
        )
    )

def get_all_tools():
    """
    Get all available tools for the agent
    
    Returns:
        List of Tool objects
    """
    tools = [
        create_calculator_tool(),
        create_web_search_tool(),
        create_document_search_tool(),
        create_document_list_tool(),
    ]
    
    logger.info(f"Initialized {len(tools)} tools for agent")
    return tools

def get_tool_names():
    """Get names of all available tools"""
    tools = get_all_tools()
    return [tool.name for tool in tools]