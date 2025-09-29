"""
Structured logging and Prometheus metrics for Character Service.
"""
import asyncio
import time
import uuid
from typing import Dict, Any, Optional, Callable
from contextvars import ContextVar

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
import structlog

# Context variables for request tracking
request_id_var: ContextVar[str] = ContextVar('request_id', default='')
user_id_var: ContextVar[str] = ContextVar('user_id', default='')

# Prometheus metrics
REQUEST_COUNT = Counter(
    'character_service_requests_total',
    'Total number of HTTP requests',
    ['method', 'endpoint', 'status_code']
)

REQUEST_DURATION = Histogram(
    'character_service_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)

ACTIVE_CONNECTIONS = Gauge(
    'character_service_active_connections',
    'Number of active connections'
)

CHARACTER_OPERATIONS = Counter(
    'character_service_operations_total',
    'Total number of character operations',
    ['operation', 'status']
)

DATABASE_OPERATIONS = Counter(
    'character_service_database_operations_total',
    'Total number of database operations',
    ['operation', 'table', 'status']
)

DATABASE_DURATION = Histogram(
    'character_service_database_duration_seconds',
    'Database operation duration in seconds',
    ['operation', 'table']
)

MCP_TOOL_CALLS = Counter(
    'character_service_mcp_tool_calls_total',
    'Total number of MCP tool calls',
    ['tool_name', 'status']
)

MCP_TOOL_DURATION = Histogram(
    'character_service_mcp_tool_duration_seconds',
    'MCP tool execution duration in seconds',
    ['tool_name']
)


def add_request_id(logger, method_name, event_dict):
    """Add request ID to log events."""
    request_id = request_id_var.get('')
    if request_id:
        event_dict['request_id'] = request_id
    return event_dict


def add_user_id(logger, method_name, event_dict):
    """Add user ID to log events."""
    user_id = user_id_var.get('')
    if user_id:
        event_dict['user_id'] = user_id
    return event_dict


def setup_observability():
    """Configure structured logging and metrics."""
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            add_request_id,
            add_user_id,
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


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware for collecting HTTP metrics and request tracking."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate request ID
        request_id = str(uuid.uuid4())
        request_id_var.set(request_id)
        
        # Extract user ID from headers if available
        user_id = request.headers.get('X-User-ID', '')
        user_id_var.set(user_id)
        
        # Track active connections
        ACTIVE_CONNECTIONS.inc()
        
        # Start timing
        start_time = time.time()
        
        # Get request details
        method = request.method
        path = request.url.path
        
        # Process request
        try:
            response = await call_next(request)
            status_code = response.status_code
            
            # Record metrics
            REQUEST_COUNT.labels(
                method=method,
                endpoint=path,
                status_code=status_code
            ).inc()
            
            duration = time.time() - start_time
            REQUEST_DURATION.labels(
                method=method,
                endpoint=path
            ).observe(duration)
            
            # Add response headers
            response.headers['X-Request-ID'] = request_id
            
            return response
            
        except Exception as e:
            # Record error metrics
            REQUEST_COUNT.labels(
                method=method,
                endpoint=path,
                status_code=500
            ).inc()
            
            duration = time.time() - start_time
            REQUEST_DURATION.labels(
                method=method,
                endpoint=path
            ).observe(duration)
            
            raise
        finally:
            # Decrement active connections
            ACTIVE_CONNECTIONS.dec()


# Middleware instance
metrics_middleware = MetricsMiddleware


def track_character_operation(operation: str, status: str = 'success'):
    """Track character operation metrics."""
    CHARACTER_OPERATIONS.labels(
        operation=operation,
        status=status
    ).inc()


def track_database_operation(operation: str, table: str, duration: float, status: str = 'success'):
    """Track database operation metrics."""
    DATABASE_OPERATIONS.labels(
        operation=operation,
        table=table,
        status=status
    ).inc()
    
    DATABASE_DURATION.labels(
        operation=operation,
        table=table
    ).observe(duration)


def track_mcp_tool_call(tool_name: str, duration: float, status: str = 'success'):
    """Track MCP tool call metrics."""
    MCP_TOOL_CALLS.labels(
        tool_name=tool_name,
        status=status
    ).inc()
    
    MCP_TOOL_DURATION.labels(
        tool_name=tool_name
    ).observe(duration)


class DatabaseMetricsWrapper:
    """Wrapper for database operations to automatically track metrics."""
    
    def __init__(self, session, table_name: str):
        self.session = session
        self.table_name = table_name
        self.logger = structlog.get_logger(__name__)
    
    async def execute_with_metrics(self, operation: str, query_func):
        """Execute database operation with automatic metrics tracking."""
        start_time = time.time()
        
        try:
            result = await query_func()
            duration = time.time() - start_time
            
            track_database_operation(operation, self.table_name, duration, 'success')
            
            self.logger.debug("Database operation completed",
                            operation=operation,
                            table=self.table_name,
                            duration_ms=round(duration * 1000, 2))
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            track_database_operation(operation, self.table_name, duration, 'error')
            
            self.logger.error("Database operation failed",
                            operation=operation,
                            table=self.table_name,
                            duration_ms=round(duration * 1000, 2),
                            error=str(e))
            raise


class MCPToolMetricsWrapper:
    """Wrapper for MCP tool calls to automatically track metrics."""
    
    def __init__(self, tool_name: str):
        self.tool_name = tool_name
        self.logger = structlog.get_logger(__name__)
    
    async def execute_with_metrics(self, tool_func):
        """Execute MCP tool with automatic metrics tracking."""
        start_time = time.time()
        
        try:
            result = await tool_func()
            duration = time.time() - start_time
            
            # Determine status from result
            status = 'success' if result.get('success', True) else 'error'
            track_mcp_tool_call(self.tool_name, duration, status)
            
            self.logger.info("MCP tool executed",
                           tool_name=self.tool_name,
                           duration_ms=round(duration * 1000, 2),
                           status=status)
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            track_mcp_tool_call(self.tool_name, duration, 'error')
            
            self.logger.error("MCP tool execution failed",
                            tool_name=self.tool_name,
                            duration_ms=round(duration * 1000, 2),
                            error=str(e))
            raise


def get_prometheus_metrics() -> str:
    """Get Prometheus metrics in text format."""
    return generate_latest()


def get_metrics_content_type() -> str:
    """Get Prometheus metrics content type."""
    return CONTENT_TYPE_LATEST


# Character Creator specific metrics
CHARACTER_CREATOR_METRICS = Counter(
    'character_creator_operations_total',
    'Character creator operations',
    ['operation', 'status']
)

CHARACTER_CREATOR_LATENCY = Histogram(
    'character_creator_latency_seconds',
    'Character creator operation latency',
    ['operation']
)


async def emit_metric(metric_name: str, value: float, labels: Optional[Dict[str, str]] = None):
    """Emit a custom metric."""
    try:
        if metric_name == "character_creator.profile_count":
            CHARACTER_CREATOR_METRICS.labels(
                operation="profile_generation",
                status="success"
            ).inc(value)
        elif metric_name == "character_creator.unresolved_reference_rate":
            # For rates, we could use a gauge instead
            pass
        elif metric_name == "character_creator.latency_ms":
            CHARACTER_CREATOR_LATENCY.labels(
                operation="profile_generation"
            ).observe(value / 1000)  # Convert ms to seconds
        elif metric_name == "character_creator.error_count":
            CHARACTER_CREATOR_METRICS.labels(
                operation="profile_generation",
                status="error"
            ).inc(value)
    except Exception as e:
        # Don't let metrics failures break the application
        logger = structlog.get_logger(__name__)
        logger.warning("Failed to emit metric", metric_name=metric_name, error=str(e))


def track_execution_time(operation_name: str):
    """Decorator to track execution time of functions."""
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    duration = time.time() - start_time
                    await emit_metric(f"{operation_name}.latency_ms", duration * 1000)
                    return result
                except Exception as e:
                    duration = time.time() - start_time
                    await emit_metric(f"{operation_name}.error_count", 1)
                    raise
            return async_wrapper
        else:
            def sync_wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    duration = time.time() - start_time
                    # Note: sync version can't emit async metrics
                    return result
                except Exception as e:
                    duration = time.time() - start_time
                    raise
            return sync_wrapper
    return decorator
