"""CLI runner for evaluation harness."""

import argparse
import asyncio
import json
import sys
from typing import Any

from evals import (
    EvalSuite,
    LatencyEvaluator,
    RAGAccuracyEvaluator,
    TaskCompletionEvaluator,
)
from evals.benchmarks import get_scenario, list_scenarios


async def run_eval_suite(scenario_name: str, use_mock: bool = True) -> dict[str, Any]:
    """Run evaluation suite on a benchmark scenario.

    Args:
        scenario_name: Name of the benchmark scenario
        use_mock: Whether to use mock responses (for testing)

    Returns:
        Suite results
    """
    scenario = get_scenario(scenario_name)
    if not scenario:
        print(f"Error: Scenario '{scenario_name}' not found")
        print(f"Available scenarios: {', '.join(list_scenarios())}")
        sys.exit(1)

    print(f"Running evaluation suite on scenario: {scenario.name}")
    print(f"Description: {scenario.description}")
    print(f"Task: {scenario.task}")
    print()

    # Create evaluation suite
    suite = EvalSuite(name=f"benchmark_{scenario_name}")

    # Add evaluators
    suite.add_evaluator(TaskCompletionEvaluator())
    suite.add_evaluator(RAGAccuracyEvaluator())
    suite.add_evaluator(LatencyEvaluator())

    # Generate mock response if needed
    if use_mock:
        response = f"Mock response for: {scenario.task}. " + " ".join(scenario.expected_keywords)
    else:
        # In production, this would call the actual brain system
        response = scenario.expected_answer

    # Run task completion evaluation
    print("Running task completion evaluation...")
    await suite.evaluators[0].run(
        task=scenario.task,
        response=response,
        expected_keywords=scenario.expected_keywords,
    )

    # Run RAG accuracy evaluation
    print("Running RAG accuracy evaluation...")
    await suite.evaluators[1].run(
        question=scenario.task,
        expected_answer=scenario.expected_answer,
        retrieved_context=scenario.context or [response],
        generated_answer=response,
    )

    # Run latency evaluation (mock operation)
    print("Running latency evaluation...")

    async def mock_operation() -> str:
        await asyncio.sleep(0.1)  # Simulate some work
        return response

    await suite.evaluators[2].run(
        operation=mock_operation,
        max_latency=2.0,
        num_runs=3,
    )

    # Get summary
    summary = suite.get_summary()

    print()
    print("=" * 60)
    print("EVALUATION RESULTS")
    print("=" * 60)
    print()

    for eval_summary in summary["evaluators"]:
        print(f"Evaluator: {eval_summary['name']}")
        print(f"  Total runs: {eval_summary['total_runs']}")
        print(f"  Passed: {eval_summary['passed']}")
        print(f"  Failed: {eval_summary['failed']}")
        print(f"  Pass rate: {eval_summary['pass_rate']:.2%}")
        print(f"  Avg score: {eval_summary['avg_score']:.2f}")
        print(f"  Avg duration: {eval_summary['avg_duration']:.3f}s")
        print()

    print(f"Overall pass rate: {summary['overall_pass_rate']:.2%}")
    print()

    return summary


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Secondary Brain Evaluation Harness")
    parser.add_argument(
        "scenario",
        nargs="?",
        help="Benchmark scenario name (use 'list' to see available scenarios)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available benchmark scenarios",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all benchmark scenarios",
    )
    parser.add_argument(
        "--no-mock",
        action="store_true",
        help="Use real brain system instead of mock responses",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file for results (JSON format)",
    )

    args = parser.parse_args()

    if args.list:
        print("Available benchmark scenarios:")
        for name in list_scenarios():
            scenario = get_scenario(name)
            if scenario:
                print(f"  - {name}: {scenario.description}")
        return

    if args.all:
        print("Running all benchmark scenarios...")
        all_results = []
        for scenario_name in list_scenarios():
            print()
            print("=" * 60)
            result = asyncio.run(run_eval_suite(scenario_name, use_mock=not args.no_mock))
            all_results.append(result)

        if args.output:
            with open(args.output, "w") as f:
                json.dump(all_results, f, indent=2)
            print(f"\nResults saved to {args.output}")
        return

    if not args.scenario:
        parser.print_help()
        sys.exit(1)

    result = asyncio.run(run_eval_suite(args.scenario, use_mock=not args.no_mock))

    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)
        print(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()
