"""
Simplified agent implementation that's compatible with all LangChain versions
Uses manual tool calling instead of AgentExecutor
"""

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from app.llm import get_llm_service
from app.tools import get_all_tools
from app.logger import setup_logger
from typing import List, Dict, Optional
import re
import json

logger = setup_logger("docuchat.agent")

class SimpleAgentService:
    """Simple agent service with manual tool calling"""
    
    def __init__(self):
        """Initialize agent service"""
        self.llm_service = get_llm_service()
        self.tools = get_all_tools()
        self.tool_map = {tool.name: tool for tool in self.tools}
        
        logger.info(
            "Simple agent service initialized",
            extra={
                "num_tools": len(self.tools),
                "tools": [tool.name for tool in self.tools]
            }
        )
    
    def _get_tool_descriptions(self) -> str:
        """Get formatted tool descriptions"""
        descriptions = []
        for tool in self.tools:
            descriptions.append(f"- {tool.name}: {tool.description}")
        return "\n".join(descriptions)
    
    def _format_chat_history(self, chat_history: List[Dict[str, str]]) -> List:
        """Convert chat history to LangChain message format"""
        messages = []
        for msg in chat_history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))
        return messages
    
    async def run_agent(
        self,
        query: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        request_id: str = None,
        max_iterations: int = 5
    ) -> Dict:
        """
        Run agent with query using manual tool calling
        
        Args:
            query: User query
            chat_history: Optional conversation history
            request_id: Request ID for logging
            max_iterations: Maximum tool call iterations
            
        Returns:
            Dict with output, tool_usage, and success status
        """
        try:
            logger.info(
                "Running simple agent",
                extra={
                    "request_id": request_id,
                    "query": query[:100],
                }
            )
            
            tool_usage = []
            iteration = 0
            
            # Build system prompt
            system_prompt = f"""You are a helpful AI assistant with access to the following tools:

{self._get_tool_descriptions()}

To use a tool, respond with:
TOOL: <tool_name>
INPUT: <tool_input>

You can use multiple tools if needed. After using tools, provide your final answer starting with "ANSWER:".

If you don't need any tools, just provide your answer directly.

Examples:
- For "What is 2+2?": Use Calculator
- For "Search for AI news": Use WebSearch  
- For "What documents do I have?": Use ListDocuments
"""
            
            # Build conversation
            messages = [SystemMessage(content=system_prompt)]
            
            if chat_history:
                messages.extend(self._format_chat_history(chat_history))
            
            messages.append(HumanMessage(content=query))
            
            # Iterative tool calling
            current_response = ""
            
            while iteration < max_iterations:
                iteration += 1
                
                # Get LLM response
                response = await self.llm_service.llm.ainvoke(messages)
                current_response = response.content
                
                # Check if tool is requested
                if "TOOL:" in current_response and "INPUT:" in current_response:
                    # Parse tool request
                    tool_match = re.search(r'TOOL:\s*(\w+)', current_response)
                    input_match = re.search(r'INPUT:\s*(.+?)(?=\n|$)', current_response, re.DOTALL)
                    
                    if tool_match and input_match:
                        tool_name = tool_match.group(1).strip()
                        tool_input = input_match.group(1).strip()
                        
                        # Execute tool
                        if tool_name in self.tool_map:
                            logger.info(
                                f"Executing tool: {tool_name}",
                                extra={"request_id": request_id, "tool": tool_name}
                            )
                            
                            tool = self.tool_map[tool_name]
                            tool_result = tool.func(tool_input)
                            
                            tool_usage.append({
                                "tool": tool_name,
                                "tool_input": tool_input,
                                "observation": str(tool_result)[:500]
                            })
                            
                            # Add tool result to conversation
                            messages.append(AIMessage(content=current_response))
                            messages.append(HumanMessage(
                                content=f"Tool result: {tool_result}\n\nNow provide your final answer."
                            ))
                            
                            continue
                        else:
                            logger.warning(
                                f"Unknown tool requested: {tool_name}",
                                extra={"request_id": request_id}
                            )
                
                # If we get here, we have a final answer
                break
            
            # Extract final answer
            if "ANSWER:" in current_response:
                final_answer = current_response.split("ANSWER:", 1)[1].strip()
            else:
                final_answer = current_response
            
            logger.info(
                "Agent execution completed",
                extra={
                    "request_id": request_id,
                    "num_tools_used": len(tool_usage),
                    "iterations": iteration
                }
            )
            
            return {
                "output": final_answer,
                "intermediate_steps": [],
                "tool_usage": tool_usage,
                "success": True
            }
            
        except Exception as e:
            logger.error(
                f"Agent execution failed: {str(e)}",
                extra={"request_id": request_id},
                exc_info=True
            )
            return {
                "output": f"I encountered an error: {str(e)}",
                "intermediate_steps": [],
                "tool_usage": [],
                "success": False,
                "error": str(e)
            }
    
    async def run_agent_stream(
        self,
        query: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        request_id: str = None
    ):
        """
        Stream agent execution
        
        Args:
            query: User query
            chat_history: Optional conversation history
            request_id: Request ID for logging
            
        Yields:
            Event dictionaries
        """
        try:
            logger.info(
                "Starting streaming agent execution",
                extra={"request_id": request_id}
            )
            
            yield {
                "type": "start",
                "data": {"status": "Agent thinking..."}
            }
            
            # For simplicity, run non-streaming and yield result
            # You can enhance this later with true streaming
            result = await self.run_agent(query, chat_history, request_id)
            
            if result["tool_usage"]:
                for tool in result["tool_usage"]:
                    yield {
                        "type": "tool_start",
                        "data": {
                            "tool": tool["tool"],
                            "input": tool["tool_input"]
                        }
                    }
                    
                    yield {
                        "type": "tool_end",
                        "data": {
                            "tool": tool["tool"],
                            "output": tool["observation"]
                        }
                    }
            
            # Stream the response
            output = result["output"]
            for i, char in enumerate(output):
                yield {
                    "type": "message",
                    "data": {"chunk": char}
                }
            
            yield {
                "type": "done",
                "data": {
                    "status": "completed",
                    "tools_used": [t["tool"] for t in result["tool_usage"]]
                }
            }
            
        except Exception as e:
            logger.error(
                f"Streaming agent failed: {str(e)}",
                extra={"request_id": request_id},
                exc_info=True
            )
            yield {
                "type": "error",
                "data": {"error": str(e)}
            }

# Global agent service instance
agent_service = None

def get_agent_service() -> SimpleAgentService:
    """Get or create global agent service instance"""
    global agent_service
    if agent_service is None:
        agent_service = SimpleAgentService()
    return agent_service