"""
MCP server setup and configuration for Character Service.
"""
import asyncio
import json
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
import structlog

from src.mcp.tools.create_character import CreateCharacterTool
from src.mcp.tools.get_character import GetCharacterTool
from src.mcp.tools.search_characters import SearchCharactersTool
from src.mcp.tools.create_relationship import CreateRelationshipTool
from src.mcp.tools.get_character_relationships import GetCharacterRelationshipsTool
from src.mcp.tools.update_character import UpdateCharacterTool
from src.mcp.tools.generate_character_profiles import GenerateCharacterProfilesTool
from src.database.connection import init_database, close_database

logger = structlog.get_logger(__name__)


class MCPCharacterServer:
    """MCP server for character service tools."""
    
    def __init__(self):
        self.server = Server("character-service")
        self.tools = {}
        self._setup_tools()
        self._setup_handlers()
    
    def _setup_tools(self):
        """Initialize and register all character tools."""
        tool_classes = [
            CreateCharacterTool,
            GetCharacterTool,
            SearchCharactersTool,
            CreateRelationshipTool,
            GetCharacterRelationshipsTool,
            UpdateCharacterTool,
            GenerateCharacterProfilesTool
        ]
        
        for tool_class in tool_classes:
            tool_instance = tool_class()
            self.tools[tool_instance.name] = tool_instance
            logger.info("Registered MCP tool", tool_name=tool_instance.name)
    
    def _setup_handlers(self):
        """Setup MCP protocol handlers."""
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """List all available character tools."""
            tools = []
            for tool_name, tool_instance in self.tools.items():
                schema = tool_instance.get_schema()
                tools.append(Tool(
                    name=schema["name"],
                    description=schema["description"],
                    inputSchema=schema["inputSchema"]
                ))
            
            logger.info("Listed MCP tools", tool_count=len(tools))
            return tools
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Execute a character tool."""
            logger.info("Executing MCP tool", tool_name=name, arguments=arguments)
            
            if name not in self.tools:
                error_msg = f"Unknown tool: {name}"
                logger.error(error_msg)
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "success": False,
                        "error": error_msg,
                        "error_type": "unknown_tool"
                    })
                )]
            
            try:
                tool_instance = self.tools[name]
                
                # Validate input if tool supports it
                if hasattr(tool_instance, 'validate_input'):
                    tool_instance.validate_input(arguments)
                
                # Execute tool
                result = await tool_instance.execute(arguments)
                
                logger.info("Tool executed successfully", 
                           tool_name=name, 
                           success=result.get('success', True))
                
                return [TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]
                
            except Exception as e:
                error_msg = f"Tool execution failed: {str(e)}"
                logger.error("Tool execution error", 
                           tool_name=name, 
                           error=str(e), 
                           exc_info=True)
                
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "success": False,
                        "error": error_msg,
                        "error_type": "execution_error"
                    })
                )]
    
    async def start(self):
        """Start the MCP server."""
        logger.info("Starting MCP Character Server")
        
        # Initialize database
        await init_database()
        logger.info("Database initialized")
        
        # Start server
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )
    
    async def shutdown(self):
        """Shutdown the MCP server."""
        logger.info("Shutting down MCP Character Server")
        await close_database()


@asynccontextmanager
async def create_mcp_server():
    """Context manager for MCP server lifecycle."""
    server = MCPCharacterServer()
    try:
        yield server
    finally:
        await server.shutdown()


async def main():
    """Main entry point for MCP server."""
    # Configure structured logging
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    logger.info("Initializing MCP Character Server")
    
    try:
        async with create_mcp_server() as server:
            await server.start()
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error("Server error", error=str(e), exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
