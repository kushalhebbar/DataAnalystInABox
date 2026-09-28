#!/usr/bin/env python
"""
Test validation script - runs all test configurations without Streamlit UI.
Directly tests the graph pipeline with different datasets and configs.
"""

import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))

from src.state import Inputs, RunState
from src.graph import build_graph
from src.logging_config import setup_logging

logger = setup_logging(name="test_runner")


def run_test(config_path: str, test_name: str) -> bool:
    """
    Run a single test configuration.
    
    Args:
        config_path: Path to test_config JSON
        test_name: Human-readable test name
    
    Returns:
        bool: True if test passed, False otherwise
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"RUNNING: {test_name}")
    logger.info(f"{'='*60}")
    
    try:
        # Load config
        with open(config_path) as f:
            config = json.load(f)
        
        logger.info(f"Config loaded: {config_path}")
        logger.info(f"  Dataset: {config['csv_path']}")
        logger.info(f"  Problem: {config['problem_statement'][:60]}...")
        logger.info(f"  Audience: {config['audience']}")
        logger.info(f"  Target: {config.get('target_column', 'None')}")
        
        # Create inputs
        inputs = Inputs(
            dataset_paths=[config['csv_path']],
            problem_statement=config['problem_statement'],
            audience=config['audience'],
            goal_type=config['goal_type'],
            success_metric=config['success_metric'],
            data_dictionary=config.get('data_dictionary'),
            target_column=config.get('target_column'),
        )
        
        # Initialize state
        state = RunState(inputs=inputs)
        logger.info("State initialized")
        
        # Build and invoke graph
        app = build_graph()
        logger.info("Graph built")
        
        logger.info("Invoking graph...")
        output = app.invoke(state)
        
        # Validate output
        if isinstance(output, dict):
            output = RunState(**output)
        
        logger.info("Pipeline completed successfully")
        logger.info(f"  Run ID: {output.config.run_id}")
        logger.info(f"  Stage: {output.stage}")
        logger.info(f"  User questions: {len(output.user_questions)}")
        logger.info(f"  Internal questions: {len(output.internal_questions)}")
        logger.info(f"  Audit entries: {len(output.audit)}")
        logger.info(f"  Errors: {len(output.errors)}")
        
        if output.errors:
            logger.warning(f"Errors encountered: {output.errors}")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Test failed with error: {str(e)}", exc_info=True)
        return False


def main():
    """Run all test configurations."""
    logger.info("TEST SUITE: DataAnalystAgentFramework")
    
    tests = [
        {
            "config": "code/tests/test_config_baseline.json",
            "name": "BASELINE TEST (Clean Data, 10 rows)"
        },
        {
            "config": "code/tests/test_config.json",
            "name": "STRESS TEST (Complex Data, 205 rows, PII, missing values, outliers)"
        },
        {
            "config": "code/tests/test_config_exploratory.json",
            "name": "EXPLORATORY TEST (Complex Data, No Target Specified)"
        },
    ]
    
    results = {}
    for test in tests:
        passed = run_test(test["config"], test["name"])
        results[test["name"]] = passed
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("TEST SUMMARY")
    logger.info(f"{'='*60}")
    
    for test_name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        logger.info(f"{status}: {test_name}")
    
    total = len(results)
    passed_count = sum(1 for p in results.values() if p)
    
    logger.info(f"\nTotal: {passed_count}/{total} tests passed")
    
    if passed_count == total:
        logger.info("\nAll tests passed")
        return 0
    else:
        logger.error(f"\n{total - passed_count} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
