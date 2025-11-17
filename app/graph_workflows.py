"""
LangGraph workflow definitions
"""

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from app.graph_state import ResearchState, ChatState, MultiDocumentState
from app.llm import get_llm_service
from app.vector_store import get_vector_store_service
from app.tools import get_all_tools
from app.logger import setup_logger
from typing import Dict, Any
import json

logger = setup_logger("docuchat.graph_workflows")

# ============================================================================
# RESEARCH WORKFLOW - Multi-step research with tools
# ============================================================================

def create_research_plan(state: ResearchState) -> ResearchState:
    """Create a research plan based on the query"""
    logger.info(f"Creating research plan for query: {state['query'][:100]}")
    
    llm = get_llm_service().llm
    
    prompt = f"""Given this query: "{state['query']}"

Create a step-by-step research plan. Consider:
1. Do we need to search documents?
2. Do we need to search the web?
3. Do we need to perform calculations?
4. What's the best order to execute these steps?

Respond with a concise plan (3-5 steps)."""
    
    response = llm.invoke([HumanMessage(content=prompt)])
    plan = response.content
    
    logger.info(f"Research plan created: {plan[:200]}")
    
    return {
        **state,
        "research_plan": plan,
        "messages": state["messages"] + [AIMessage(content=f"Research plan: {plan}")],
        "iterations": state["iterations"] + 1
    }

def search_documents(state: ResearchState) -> ResearchState:
    """Search documents if needed"""
    logger.info("Searching documents")
    
    # Check if we should search documents
    if "document" not in state["query"].lower() and "file" not in state["query"].lower():
        logger.info("Skipping document search - not relevant")
        return state
    
    try:
        vector_store = get_vector_store_service()
        documents = vector_store.list_documents()
        
        if documents:
            results = vector_store.search(state["query"], k=3)
            docs_content = "\n\n".join([
                f"[{doc.metadata.get('filename')}]: {doc.page_content[:200]}"
                for doc in results
            ])
            
            logger.info(f"Found {len(results)} relevant document chunks")
            
            return {
                **state,
                "documents_found": documents,
                "messages": state["messages"] + [
                    AIMessage(content=f"Found relevant info in documents:\n{docs_content}")
                ]
            }
        else:
            logger.info("No documents available")
            return {
                **state,
                "documents_found": [],
                "messages": state["messages"] + [
                    AIMessage(content="No documents found in the system.")
                ]
            }
    except Exception as e:
        logger.error(f"Document search failed: {str(e)}")
        return {
            **state,
            "error": f"Document search error: {str(e)}"
        }

def search_web(state: ResearchState) -> ResearchState:
    """Search web if needed"""
    logger.info("Checking if web search is needed")
    
    # Check if web search is relevant
    if any(word in state["query"].lower() for word in ["current", "latest", "recent", "news", "today"]):
        try:
            from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
            
            logger.info("Performing web search")
            search = DuckDuckGoSearchAPIWrapper(max_results=2)
            results = search.run(state["query"])
            
            return {
                **state,
                "web_results": results,
                "messages": state["messages"] + [
                    AIMessage(content=f"Web search results: {results[:300]}...")
                ]
            }
        except Exception as e:
            logger.error(f"Web search failed: {str(e)}")
            return {
                **state,
                "error": f"Web search error: {str(e)}"
            }
    else:
        logger.info("Skipping web search - not needed")
        return state

def perform_calculations(state: ResearchState) -> ResearchState:
    """Perform calculations if needed"""
    logger.info("Checking if calculations are needed")
    
    # Check if calculations are needed
    if any(word in state["query"].lower() for word in ["calculate", "compute", "how many", "what is", "+"]):
        try:
            import numexpr
            
            # Simple calculation detection
            llm = get_llm_service().llm
            prompt = f"""Extract any mathematical expression from this query: "{state['query']}"
If there's a calculation, respond with ONLY the expression (e.g., "2+2", "sqrt(16)").
If no calculation is needed, respond with "NONE"."""
            
            response = llm.invoke([HumanMessage(content=prompt)])
            expression = response.content.strip()
            
            if expression != "NONE" and expression:
                logger.info(f"Calculating: {expression}")
                result = numexpr.evaluate(expression).item()
                
                return {
                    **state,
                    "calculations": {"expression": expression, "result": result},
                    "messages": state["messages"] + [
                        AIMessage(content=f"Calculation: {expression} = {result}")
                    ]
                }
        except Exception as e:
            logger.error(f"Calculation failed: {str(e)}")
    
    return state

def synthesize_answer(state: ResearchState) -> ResearchState:
    """Synthesize final answer from all gathered information"""
    logger.info("Synthesizing final answer")
    
    llm = get_llm_service().llm
    
    # Build context from all gathered information
    context_parts = [f"Original query: {state['query']}"]
    
    if state.get("documents_found"):
        context_parts.append(f"Documents available: {', '.join(state['documents_found'])}")
    
    if state.get("web_results"):
        context_parts.append(f"Web results: {state['web_results'][:500]}")
    
    if state.get("calculations"):
        calc = state['calculations']
        context_parts.append(f"Calculation: {calc['expression']} = {calc['result']}")
    
    context = "\n\n".join(context_parts)
    
    prompt = f"""Based on the research gathered:

{context}

Provide a comprehensive answer to the original query. Synthesize all the information into a clear, well-structured response."""
    
    response = llm.invoke([HumanMessage(content=prompt)])
    final_answer = response.content
    
    logger.info("Final answer synthesized")
    
    return {
        **state,
        "final_answer": final_answer,
        "messages": state["messages"] + [AIMessage(content=final_answer)]
    }

def should_continue_research(state: ResearchState) -> str:
    """Decide if research should continue"""
    if state.get("error"):
        return "error"
    
    if state["iterations"] >= 5:
        return "synthesize"
    
    # If we have gathered enough information, synthesize
    has_info = any([
        state.get("documents_found"),
        state.get("web_results"),
        state.get("calculations")
    ])
    
    if has_info:
        return "synthesize"
    
    return "continue"

def create_research_workflow():
    """Create a research workflow graph"""
    workflow = StateGraph(ResearchState)
    
    # Add nodes
    workflow.add_node("plan", create_research_plan)
    workflow.add_node("search_docs", search_documents)
    workflow.add_node("search_web", search_web)
    workflow.add_node("calculate", perform_calculations)
    workflow.add_node("synthesize", synthesize_answer)
    
    # Set entry point
    workflow.set_entry_point("plan")
    
    # Add edges
    workflow.add_edge("plan", "search_docs")
    workflow.add_edge("search_docs", "search_web")
    workflow.add_edge("search_web", "calculate")
    
    # Conditional edge from calculate
    workflow.add_conditional_edges(
        "calculate",
        should_continue_research,
        {
            "continue": "synthesize",
            "synthesize": "synthesize",
            "error": END
        }
    )
    
    workflow.add_edge("synthesize", END)
    
    return workflow.compile()

# ============================================================================
# CONVERSATIONAL WORKFLOW - Smart chat with context
# ============================================================================

def analyze_query(state: ChatState) -> ChatState:
    """Analyze what resources are needed for the query"""
    logger.info(f"Analyzing query: {state['current_query'][:100]}")
    
    llm = get_llm_service().llm
    
    prompt = f"""Analyze this query: "{state['current_query']}"

Should we:
1. Search documents? (Yes if asking about uploaded files)
2. Search web? (Yes if asking about current events or facts)

Respond with JSON:
{{"search_docs": true/false, "search_web": true/false}}"""
    
    response = llm.invoke([HumanMessage(content=prompt)])
    
    try:
        analysis = json.loads(response.content)
        should_search_docs = analysis.get("search_docs", False)
        should_search_web = analysis.get("search_web", False)
    except:
        # Fallback to keyword detection
        query_lower = state['current_query'].lower()
        should_search_docs = any(word in query_lower for word in ["document", "file", "uploaded"])
        should_search_web = any(word in query_lower for word in ["current", "latest", "search", "news"])
    
    logger.info(f"Analysis: docs={should_search_docs}, web={should_search_web}")
    
    return {
        **state,
        "should_search_docs": should_search_docs,
        "should_search_web": should_search_web
    }

def route_query(state: ChatState) -> str:
    """Route to appropriate processing"""
    if state["should_search_docs"]:
        return "fetch_context"
    elif state["should_search_web"]:
        return "search_web"
    else:
        return "generate"

def fetch_document_context(state: ChatState) -> ChatState:
    """Fetch relevant document context"""
    logger.info("Fetching document context")
    
    try:
        vector_store = get_vector_store_service()
        results = vector_store.search(state["current_query"], k=3)
        
        if results:
            context = "\n\n".join([
                f"[{doc.metadata.get('filename')}]: {doc.page_content}"
                for doc in results
            ])
            logger.info(f"Retrieved {len(results)} document chunks")
        else:
            context = "No relevant documents found."
    except Exception as e:
        logger.error(f"Document fetch failed: {str(e)}")
        context = f"Error fetching documents: {str(e)}"
    
    return {
        **state,
        "context": context
    }

def generate_response(state: ChatState) -> ChatState:
    """Generate final response"""
    logger.info("Generating response")
    
    llm = get_llm_service().llm
    
    messages = state["messages"].copy()
    
    if state.get("context"):
        messages.append(SystemMessage(
            content=f"Relevant context:\n{state['context']}\n\nUse this context to answer the query."
        ))
    
    messages.append(HumanMessage(content=state["current_query"]))
    
    response = llm.invoke(messages)
    
    return {
        **state,
        "response": response.content,
        "messages": state["messages"] + [
            HumanMessage(content=state["current_query"]),
            AIMessage(content=response.content)
        ]
    }

def create_chat_workflow():
    """Create a conversational workflow graph"""
    workflow = StateGraph(ChatState)
    
    # Add nodes
    workflow.add_node("analyze", analyze_query)
    workflow.add_node("fetch_context", fetch_document_context)
    workflow.add_node("generate", generate_response)
    
    # Set entry point
    workflow.set_entry_point("analyze")
    
    # Add conditional routing
    workflow.add_conditional_edges(
        "analyze",
        route_query,
        {
            "fetch_context": "fetch_context",
            "search_web": "generate",  # Simplified - could add web search node
            "generate": "generate"
        }
    )
    
    workflow.add_edge("fetch_context", "generate")
    workflow.add_edge("generate", END)
    
    return workflow.compile()

# Export compiled workflows
research_workflow = None
chat_workflow = None

def get_research_workflow():
    """Get or create research workflow"""
    global research_workflow
    if research_workflow is None:
        research_workflow = create_research_workflow()
        logger.info("Research workflow created")
    return research_workflow

def get_chat_workflow():
    """Get or create chat workflow"""
    global chat_workflow
    if chat_workflow is None:
        chat_workflow = create_chat_workflow()
        logger.info("Chat workflow created")
    return chat_workflow