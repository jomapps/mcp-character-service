"""
Health check endpoints and service monitoring for Character Service.
"""
import asyncio
import time
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import structlog

from src.database.connection import get_database_session, DatabaseError
from src.services.character_service import CharacterService

logger = structlog.get_logger(__name__)

router = APIRouter()


class HealthStatus(BaseModel):
    """Health status response model."""
    status: str
    timestamp: str
    version: str
    uptime_seconds: float
    checks: Dict[str, Any]


class DatabaseHealthCheck(BaseModel):
    """Database health check details."""
    status: str
    response_time_ms: float
    connection_pool_size: Optional[int] = None
    active_connections: Optional[int] = None


class ServiceHealthCheck(BaseModel):
    """Service health check details."""
    status: str
    memory_usage_mb: Optional[float] = None
    cpu_usage_percent: Optional[float] = None


# Track service start time for uptime calculation
SERVICE_START_TIME = time.time()


async def check_database_health() -> DatabaseHealthCheck:
    """Check database connectivity and performance."""
    start_time = time.time()
    
    try:
        async with get_database_session() as session:
            # Simple query to test database connectivity
            character_service = CharacterService(session)
            
            # Test a basic database operation
            await session.execute("SELECT 1")
            
            response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            return DatabaseHealthCheck(
                status="healthy",
                response_time_ms=round(response_time, 2)
            )
            
    except DatabaseError as e:
        logger.error("Database health check failed", error=str(e))
        response_time = (time.time() - start_time) * 1000
        return DatabaseHealthCheck(
            status="unhealthy",
            response_time_ms=round(response_time, 2)
        )
    except Exception as e:
        logger.error("Database health check error", error=str(e))
        response_time = (time.time() - start_time) * 1000
        return DatabaseHealthCheck(
            status="error",
            response_time_ms=round(response_time, 2)
        )


async def check_service_health() -> ServiceHealthCheck:
    """Check service-level health metrics."""
    try:
        # Basic service health - could be extended with actual metrics
        return ServiceHealthCheck(
            status="healthy"
        )
    except Exception as e:
        logger.error("Service health check error", error=str(e))
        return ServiceHealthCheck(
            status="error"
        )


@router.get("/", response_model=HealthStatus)
async def health_check():
    """
    Comprehensive health check endpoint.
    
    Returns overall service health including database connectivity,
    service metrics, and dependency status.
    """
    logger.info("Performing health check")
    
    start_time = time.time()
    uptime = time.time() - SERVICE_START_TIME
    
    # Run health checks concurrently
    try:
        db_health, service_health = await asyncio.gather(
            check_database_health(),
            check_service_health(),
            return_exceptions=True
        )
        
        # Handle exceptions from health checks
        if isinstance(db_health, Exception):
            logger.error("Database health check failed", error=str(db_health))
            db_health = DatabaseHealthCheck(
                status="error",
                response_time_ms=0
            )
        
        if isinstance(service_health, Exception):
            logger.error("Service health check failed", error=str(service_health))
            service_health = ServiceHealthCheck(
                status="error"
            )
        
        # Determine overall status
        overall_status = "healthy"
        if db_health.status != "healthy" or service_health.status != "healthy":
            overall_status = "degraded"
        if db_health.status == "error" or service_health.status == "error":
            overall_status = "unhealthy"
        
        health_response = HealthStatus(
            status=overall_status,
            timestamp=datetime.utcnow().isoformat(),
            version="1.0.0",
            uptime_seconds=round(uptime, 2),
            checks={
                "database": db_health.dict(),
                "service": service_health.dict()
            }
        )
        
        total_time = (time.time() - start_time) * 1000
        logger.info("Health check completed", 
                   status=overall_status,
                   duration_ms=round(total_time, 2))
        
        return health_response
        
    except Exception as e:
        logger.error("Health check failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Health check failed"
        )


@router.get("/ready")
async def readiness_check():
    """
    Readiness check endpoint for Kubernetes/container orchestration.
    
    Returns 200 if service is ready to accept traffic, 503 otherwise.
    """
    try:
        # Check if database is accessible
        db_health = await check_database_health()
        
        if db_health.status == "healthy":
            return {"status": "ready", "timestamp": datetime.utcnow().isoformat()}
        else:
            raise HTTPException(
                status_code=503,
                detail="Service not ready - database unavailable"
            )
            
    except Exception as e:
        logger.error("Readiness check failed", error=str(e))
        raise HTTPException(
            status_code=503,
            detail="Service not ready"
        )


@router.get("/live")
async def liveness_check():
    """
    Liveness check endpoint for Kubernetes/container orchestration.
    
    Returns 200 if service is alive, 503 if it should be restarted.
    """
    try:
        # Basic liveness check - service is responding
        uptime = time.time() - SERVICE_START_TIME
        
        return {
            "status": "alive",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": round(uptime, 2)
        }
        
    except Exception as e:
        logger.error("Liveness check failed", error=str(e))
        raise HTTPException(
            status_code=503,
            detail="Service not alive"
        )


@router.get("/metrics")
async def metrics_endpoint():
    """
    Basic metrics endpoint for monitoring.
    
    Returns service metrics in a simple JSON format.
    Could be extended to return Prometheus format.
    """
    try:
        uptime = time.time() - SERVICE_START_TIME
        
        # Get database health for metrics
        db_health = await check_database_health()
        
        metrics = {
            "service_uptime_seconds": round(uptime, 2),
            "service_start_time": SERVICE_START_TIME,
            "database_response_time_ms": db_health.response_time_ms,
            "database_status": db_health.status,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return metrics
        
    except Exception as e:
        logger.error("Metrics endpoint failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Metrics unavailable"
        )
