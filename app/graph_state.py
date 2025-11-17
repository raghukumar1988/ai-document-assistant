"""
State definitions for LangGraph workflows
"""

from typing import TypedDict, List, Optional, Dict, Any, Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

class ResearchState(TypedDict):
    """State for research workflow"""
    query: str  # Original user query
    messages: Annotated[List[BaseMessage], add_messages]  # Conversation history
    documents_found: List[str]  # Document filenames found
    web_results: Optional[str]  # Web search results
    calculations: Optional[Dict[str, Any]]  # Calculation results
    research_plan: Optional[str]  # Research plan
    final_answer: Optional[str]  # Final synthesized answer
    iterations: int  # Number of workflow iterations
    needs_approval: bool  # Whether human approval is needed
    approved: Optional[bool]  # Human approval status
    error: Optional[str]  # Error message if any

class ChatState(TypedDict):
    """State for conversational workflow"""
    messages: Annotated[List[BaseMessage], add_messages]  # Message history
    current_query: str  # Current user query
    context: Optional[str]  # Retrieved context
    response: Optional[str]  # Generated response
    should_search_docs: bool  # Whether to search documents
    should_search_web: bool  # Whether to search web

class MultiDocumentState(TypedDict):
    """State for multi-document analysis workflow"""
    query: str  # Analysis query
    messages: Annotated[List[BaseMessage], add_messages]
    documents: List[str]  # List of document names to analyze
    document_summaries: Dict[str, str]  # Summaries per document
    comparisons: Optional[str]  # Document comparisons
    synthesis: Optional[str]  # Final synthesis
    current_doc_index: int  # Current document being processed
    total_docs: int  # Total documents to process
    error: Optional[str]

class WorkflowMetadata(TypedDict):
    """Metadata for workflow execution"""
    workflow_id: str
    workflow_type: str
    started_at: str
    completed_at: Optional[str]
    status: str  # running, completed, failed, needs_approval
    steps_executed: List[str]
    total_steps: int
    current_step: int