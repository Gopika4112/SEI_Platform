import os
import sys
import tempfile
import shutil

# Ensure the project root is in the Python search path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests.test_parser import test_pipeline_integration
from tests.test_retrieval import test_vector_store_manager_mock, test_graph_store_manager_mock
from tests.test_agents import (
    test_planner_agent_mock,
    test_retriever_agent_mock,
    test_graph_agent_mock,
    test_answer_agent_mock,
    test_evaluator_agent_mock,
    test_graph_flow_compiles
)

if __name__ == "__main__":
    print("Running integration tests using local virtual environment dependencies...")
    
    # Run Phase 4 Mock Tests
    print("Running Phase 4 Agent Mock Tests...")
    try:
        test_planner_agent_mock()
        test_retriever_agent_mock()
        test_graph_agent_mock()
        test_answer_agent_mock()
        test_evaluator_agent_mock()
        test_graph_flow_compiles()
        print("SUCCESS: Phase 4 Agent Mock Tests passed successfully!")
    except AssertionError as e:
        print("FAILURE: Assertion error in Phase 4 Agent Mock Tests:")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Run Phase 2 Mock Tests
    print("Running Phase 2 Storage Mock Tests...")
    try:
        test_vector_store_manager_mock()
        test_graph_store_manager_mock()
        print("SUCCESS: Phase 2 Storage Mock Tests passed successfully!")
    except AssertionError as e:
        print("FAILURE: Assertion error in Phase 2 Mock Tests:")
        import traceback
        traceback.print_exc()
        sys.exit(1)
        
    # Run Phase 1 Integration Tests
    print("Running Phase 1 Ingestion Integration Tests...")
    tmp_dir = tempfile.mkdtemp()
    try:
        test_pipeline_integration(tmp_dir)
        print("SUCCESS: Phase 1 Ingestion Integration Tests passed successfully!")
        sys.exit(0)
    except AssertionError as e:
        print("FAILURE: Assertion error in tests:")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print("ERROR: Unexpected error running tests:")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        shutil.rmtree(tmp_dir)
