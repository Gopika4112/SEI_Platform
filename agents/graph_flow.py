import os
import logging
from typing import Dict, Any, List, TypedDict, Literal
from langgraph.graph import StateGraph, END

logger = logging.getLogger(__name__)

# Import core agents
from agents.planner import PlannerAgent
from agents.retriever import RetrieverAgent
from agents.graph_agent import GraphAgent
from agents.answer import AnswerAgent
from agents.evaluator import EvaluatorAgent

# Import retrievers
from storage.vector_store import VectorStoreManager
from storage.graph_store import GraphStoreManager
from storage.embedder import CodeEmbedder
from retrieval.semantic import SemanticRetriever
from retrieval.graph import GraphRetriever
from retrieval.hybrid import HybridRetriever

# Define shared State Schema utilizing TypedDict
class AgentState(TypedDict):
    query: str
    intent: str
    entities: List[str]
    vector_results: List[Dict[str, Any]]
    graph_results: List[Dict[str, Any]]
    answer: str
    sources: List[str]
    eval_score: float
    eval_feedback: str
    retry_count: int

# Initialize shared backend instances
# (These will automatically connect to local localhost docker ports)
embedder = None
vector_store = None
graph_store = None
semantic_retriever = None
graph_retriever = None
hybrid_retriever = None

def get_pipeline_instances():
    """Lazy initializer for database clients and retrieval managers."""
    global embedder, vector_store, graph_store, semantic_retriever, graph_retriever, hybrid_retriever
    if semantic_retriever is None:
        if embedder is None:
            embedder = CodeEmbedder()
        vector_store = VectorStoreManager()
        graph_store = GraphStoreManager()
        semantic_retriever = SemanticRetriever(vector_store, embedder)
        graph_retriever = GraphRetriever(graph_store)
        hybrid_retriever = HybridRetriever(semantic_retriever, graph_retriever)
    return semantic_retriever, graph_retriever, hybrid_retriever

# ----------------- LANGGRAPH NODE FUNCTIONS -----------------

def planner_node(state: AgentState) -> Dict[str, Any]:
    """Classifies query intent and extracts target code entities."""
    planner = PlannerAgent()
    plan_result = planner.plan(state["query"])
    return {
        "intent": plan_result["intent"],
        "entities": plan_result["entities"],
        "retry_count": 0
    }

def retriever_node(state: AgentState) -> Dict[str, Any]:
    """Retrieves similar vector chunks from Qdrant."""
    semantic_ret, _, _ = get_pipeline_instances()
    agent = RetrieverAgent(semantic_ret)
    res = agent.execute(state)
    return {"vector_results": res.get("vector_results", [])}

def graph_node(state: AgentState) -> Dict[str, Any]:
    """Traverses related call chains/inheritance in Neo4j."""
    _, graph_ret, _ = get_pipeline_instances()
    agent = GraphAgent(graph_ret)
    res = agent.execute(state)
    return {"graph_results": res.get("graph_results", [])}

def answer_node(state: AgentState) -> Dict[str, Any]:
    """Synthesizes markdown answer grounded in file scopes."""
    _, _, hybrid_ret = get_pipeline_instances()
    agent = AnswerAgent(hybrid_ret)
    res_state = agent.execute_synthesis = agent.synthesize(state)
    # Increment loop retries count
    res_state["retry_count"] = state.get("retry_count", 0) + 1
    return res_state

def evaluator_node(state: AgentState) -> Dict[str, Any]:
    """Scores answer correctness and flags hallucinations."""
    agent = EvaluatorAgent()
    return agent.evaluate(state)

# ----------------- ROUTING DECISIONS -----------------

def route_from_planner(state: AgentState) -> List[str]:
    """Routes to retriever, graph agent, or both in parallel based on intent."""
    intent = state.get("intent", "explain")
    if intent in ("search", "docs"):
        return ["retriever"]
    elif intent in ("impact", "trace"):
        return ["graph_agent"]
    else:
        # Fork in parallel to retrieve both semantic and graph contexts
        return ["retriever", "graph_agent"]

def route_from_evaluator(state: AgentState) -> Literal["answer", "__end__"]:
    """Conditional self-correcting loop back to Answer node if score is low."""
    score = state.get("eval_score", 1.0)
    retry_count = state.get("retry_count", 0)
    
    if score < 0.6 and retry_count < 2:
        logger.warning(f"Answer failed evaluation (Score: {score}). Routing back to AnswerAgent for correction.")
        return "answer"
    return END

# ----------------- WORKFLOW CONSTRUCTOR -----------------

def build_workflow() -> StateGraph:
    """Constructs the LangGraph state machine workflow with parallel forking and self-correcting loops."""
    workflow = StateGraph(AgentState)
    
    # 1. Add all agent nodes
    workflow.add_node("planner", planner_node)
    workflow.add_node("retriever", retriever_node)
    workflow.add_node("graph_agent", graph_node)
    workflow.add_node("answer", answer_node)
    workflow.add_node("evaluator", evaluator_node)
    
    # 2. Configure Entry Point
    workflow.set_entry_point("planner")
    
    # 3. Add Conditional Router from Planner Node
    workflow.add_conditional_edges(
        "planner",
        route_from_planner,
        {
            "retriever": "retriever",
            "graph_agent": "graph_agent"
        }
    )
    
    # 4. Add Join edges to Answer Node
    workflow.add_edge("retriever", "answer")
    workflow.add_edge("graph_agent", "answer")
    
    # 5. Connect Answer to Evaluator
    workflow.add_edge("answer", "evaluator")
    
    # 6. Add Conditional Router from Evaluator (Corrective Loop)
    workflow.add_conditional_edges(
        "evaluator",
        route_from_evaluator,
        {
            "answer": "answer",
            END: END
        }
    )
    
    return workflow
