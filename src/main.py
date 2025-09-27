"""
FastAPI application setup with MCP server integration for Character Service.
"""
import asyncio
import os
import signal
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog
import uvicorn

from src.database.connection import init_database, close_database, get_database_session
from src.mcp.server import MCPCharacterServer
from src.api.health import router as health_router
from src.utils.observability import setup_observability, metrics_middleware

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    logger.info("Starting Character Service application")
    
    # Initialize database
    await init_database()
    logger.info("Database initialized")
    
    # Setup observability
    setup_observability()
    logger.info("Observability configured")
    
    # Initialize MCP server (but don't start it - it runs separately)
    app.state.mcp_server = MCPCharacterServer()
    logger.info("MCP server initialized")
    
    yield
    
    # Cleanup
    logger.info("Shutting down Character Service application")
    await close_database()
    if hasattr(app.state, 'mcp_server'):
        await app.state.mcp_server.shutdown()


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="MCP Character Service",
        description="A microservice providing MCP-compliant tools for character management",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add metrics middleware
    app.add_middleware(metrics_middleware)
    
    # Include routers
    app.include_router(health_router, prefix="/health", tags=["health"])
    
    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        logger.error("Unhandled exception", 
                    path=request.url.path,
                    method=request.method,
                    error=str(exc),
                    exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "message": "An unexpected error occurred"
            }
        )
    
    return app


# Create the FastAPI app instance
app = create_app()


@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "MCP Character Service",
        "version": "1.0.0",
        "description": "A microservice providing MCP-compliant tools for character management",
        "mcp_tools": [
            "create_character",
            "get_character", 
            "search_characters",
            "create_relationship",
            "get_character_relationships",
            "update_character"
        ],
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "redoc": "/redoc"
        }
    }


@app.get("/mcp/tools")
async def list_mcp_tools():
    """List available MCP tools."""
    if hasattr(app.state, 'mcp_server'):
        tools = []
        for tool_name, tool_instance in app.state.mcp_server.tools.items():
            schema = tool_instance.get_schema()
            tools.append({
                "name": schema["name"],
                "description": schema["description"],
                "input_schema": schema["inputSchema"],
                "output_schema": schema.get("outputSchema")
            })
        return {"tools": tools}
    else:
        raise HTTPException(status_code=503, detail="MCP server not initialized")


async def run_mcp_server():
    """Run the MCP server in a separate process/thread."""
    logger.info("Starting MCP server")
    mcp_server = MCPCharacterServer()
    await mcp_server.start()


def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown."""
    def signal_handler(signum, frame):
        logger.info("Received shutdown signal", signal=signum)
        # FastAPI will handle the shutdown via lifespan
        
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


async def main():
    """Main entry point for running both FastAPI and MCP server."""
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
    
    setup_signal_handlers()
    
    # Get configuration from environment
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8011"))
    log_level = os.getenv("LOG_LEVEL", "info")
    
    logger.info("Starting Character Service", host=host, port=port)
    
    # Run FastAPI server
    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level=log_level,
        access_log=True,
        reload=False  # Set to True for development
    )
    
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
