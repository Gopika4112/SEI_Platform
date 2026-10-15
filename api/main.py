from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from api.routes import ingest, query
from contextlib import asynccontextmanager
from storage.embedder import CodeEmbedder
from agents import graph_flow
import os

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize global embedder
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key or api_key == "your_nvidia_api_key_here":
        raise ValueError("NVIDIA_API_KEY is not set or is still the placeholder. Please set it in your .env file.")
    
    global_embedder = CodeEmbedder()
    app.state.embedder = global_embedder
    # Inject it directly into graph_flow to prevent redundant local / remote loads
    graph_flow.embedder = global_embedder
    yield

app = FastAPI(
    title="CodeAtlas API",
    description="Multi-Agent Code Intelligence System using Graph RAG",
    version="1.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(ingest.router, prefix="/api", tags=["Ingest"])
app.include_router(query.router, prefix="/api", tags=["Query"])

# Register Global Exception Handlers
@app.exception_handler(Exception)
def global_exception_handler(request: Request, exc: Exception):
    exc_str = str(exc)
    # Catch database offline/connection failure exceptions
    if any(keyword in exc_str.lower() for keyword in ("qdrant", "neo4j", "connection refused", "connection pool")):
        return JSONResponse(
            status_code=503,
            content={"detail": "Database service is offline. Please make sure Qdrant and Neo4j are running in Docker."}
        )
    # Default unhandled exception wrapper
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal Server Error: {exc_str}"}
    )

import os
from qdrant_client import QdrantClient
from neo4j import GraphDatabase

@app.get("/health")
def health_check():
    """
    Pings local Qdrant and Neo4j instances to check health, and verifies
    if the GROQ_API_KEY and NVIDIA_API_KEY are configured.
    Delegates to the implementation in query router to maintain consistency.
    """
    return query.health_check()
