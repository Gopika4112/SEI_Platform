import pytest
from unittest.mock import MagicMock, patch
from agents.planner import PlannerAgent
from agents.retriever import RetrieverAgent
from agents.graph_agent import GraphAgent
from agents.answer import AnswerAgent
from agents.evaluator import EvaluatorAgent
from agents.graph_flow import build_workflow, AgentState

def test_planner_agent_mock():
    # Test fallback extraction when Groq is not configured
    with patch.dict('os.environ', {'GROQ_API_KEY': ''}):
        planner = PlannerAgent(api_key=None)
        planner.groq_client = None
        res = planner.plan("Find calls to AuthService in code_module")
        
        assert res["intent"] == "explain"
        assert "AuthService" in res["entities"]

def test_retriever_agent_mock():
    mock_ret = MagicMock()
    mock_ret.retrieve.return_value = [{"id": "c1", "content": "class A: pass", "metadata": {}}]
    
    agent = RetrieverAgent(mock_ret)
    state = {"query": "Find Class A", "intent": "search", "entities": ["Class A"]}
    updated_state = agent.execute(state)
    
    assert "vector_results" in updated_state
    assert len(updated_state["vector_results"]) == 1
    assert updated_state["vector_results"][0]["id"] == "c1"

def test_graph_agent_mock():
    mock_ret = MagicMock()
    mock_ret.find_callers.return_value = [{"file_path": "auth.py", "name": "AuthService", "entity_type": "Class"}]
    mock_ret.find_inheritance.return_value = []
    
    agent = GraphAgent(mock_ret)
    state = {"intent": "impact", "entities": ["AuthService"]}
    updated_state = agent.execute(state)
    
    assert "graph_results" in updated_state
    assert len(updated_state["graph_results"]) == 1
    assert updated_state["graph_results"][0]["name"] == "AuthService"

def test_answer_agent_mock():
    mock_hybrid = MagicMock()
    mock_hybrid.format_context.return_value = "Mocked context block."
    
    with patch("agents.answer.Groq") as MockGroq:
        mock_client = MockGroq.return_value
        mock_msg = MagicMock()
        mock_msg.content = "Based on [auth.py], here is the answer.\n\n### Cited Source Files:\n- [auth.py]"
        mock_client.chat.completions.create.return_value.choices[0].message = mock_msg
        
        agent = AnswerAgent(mock_hybrid, api_key="mock_key")
        state = {
            "query": "Explain AuthService",
            "intent": "explain",
            "entities": ["AuthService"],
            "vector_results": [],
            "graph_results": []
        }
        updated_state = agent.synthesize(state)
        
        assert updated_state["answer"] == mock_msg.content
        assert updated_state["sources"] == ["auth.py"]

def test_evaluator_agent_mock():
    with patch("agents.evaluator.Groq") as MockGroq:
        mock_client = MockGroq.return_value
        mock_msg = MagicMock()
        mock_msg.content = '{"score": 0.95, "feedback": "Answer is fully supported by context."}'
        mock_client.chat.completions.create.return_value.choices[0].message = mock_msg
        
        agent = EvaluatorAgent(api_key="mock_key")
        state = {
            "query": "Explain AuthService",
            "answer": "Grounded answer text.",
            "vector_results": [{"id": "c1", "content": "source code content", "metadata": {"file_path": "auth.py"}}],
            "graph_results": []
        }
        updated_state = agent.evaluate(state)
        
        assert updated_state["eval_score"] == 0.95
        assert "supported by context" in updated_state["eval_feedback"]

def test_graph_flow_compiles():
    workflow = build_workflow()
    compiled_flow = workflow.compile()
    assert compiled_flow is not None
