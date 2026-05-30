from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from context_lab.cases import available_cases, load_case
from context_lab.evaluation import compare_strategies, evaluate_case
from context_lab.models import Budget
from context_lab.strategies import available_strategies


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m context_lab")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list-cases", help="사용 가능한 학습 케이스를 출력합니다.")
    subparsers.add_parser("list-strategies", help="사용 가능한 context 전략을 출력합니다.")

    run_parser = subparsers.add_parser("run", help="하나의 케이스를 하나의 전략으로 실행합니다.")
    _add_common_run_args(run_parser)
    run_parser.add_argument("--strategy", required=True, choices=available_strategies())
    run_parser.add_argument("--show-context", action="store_true")

    compare_parser = subparsers.add_parser("compare", help="하나의 케이스에서 여러 전략을 비교합니다.")
    _add_common_run_args(compare_parser)
    compare_parser.add_argument(
        "--strategies",
        nargs="+",
        default=["full_history", "sliding_window", "summary", "structured", "rag", "hybrid"],
        choices=available_strategies(),
    )

    args = parser.parse_args(argv)

    if args.command == "list-cases":
        for case_id in available_cases():
            session, _ = load_case(case_id)
            print(f"{case_id}: {session.notes}")
        return 0

    if args.command == "list-strategies":
        for strategy in available_strategies():
            print(strategy)
        return 0

    budget = Budget(max_input_tokens=args.max_input_tokens, reserved_output_tokens=args.reserved_output_tokens)

    if args.command == "run":
        result = evaluate_case(args.case, args.strategy, mode=args.mode, budget=budget)
        if args.format == "json":
            print(json.dumps(_result_to_dict(result), ensure_ascii=False, indent=2))
        else:
            _print_run(result, show_context=args.show_context)
        return 0 if result.passed else 2

    if args.command == "compare":
        results = compare_strategies(args.case, args.strategies, mode=args.mode, budget=budget)
        if args.format == "json":
            print(json.dumps([_result_to_dict(result) for result in results], ensure_ascii=False, indent=2))
        else:
            _print_table([result.row() for result in results])
        return 0

    return 1


def _add_common_run_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--case", required=True, choices=available_cases())
    parser.add_argument("--mode", choices=["mock", "openai"], default="mock")
    parser.add_argument("--max-input-tokens", type=int, default=900)
    parser.add_argument("--reserved-output-tokens", type=int, default=200)
    parser.add_argument("--format", choices=["text", "json"], default="text")


def _print_run(result, show_context: bool = False) -> None:
    print(f"case={result.case_id}")
    print(f"strategy={result.strategy}")
    print(f"mode={result.mode}")
    print(f"tokens={result.context.estimated_tokens}")
    print(f"latency_ms={result.context.latency_ms:.2f}")
    print(f"sections={', '.join(result.context.section_labels())}")
    if result.context.warnings:
        print(f"warnings={', '.join(result.context.warnings)}")
    print(f"passed={result.passed}")
    if result.missing_expected:
        print(f"missing_expected={', '.join(result.missing_expected)}")
    if result.unsafe_found:
        print(f"unsafe_found={', '.join(result.unsafe_found)}")
    if show_context:
        print("\n--- context ---")
        print(result.context.render())
    print("\n--- answer ---")
    print(result.generation.text)


def _print_table(rows: list[dict[str, str | int | float | bool]]) -> None:
    if not rows:
        return
    headers = ["strategy", "tokens", "latency_ms", "passed", "missing", "unsafe", "warnings"]
    widths = {
        header: max(len(header), *(len(str(row[header])) for row in rows))
        for header in headers
    }
    print(" | ".join(header.ljust(widths[header]) for header in headers))
    print("-+-".join("-" * widths[header] for header in headers))
    for row in rows:
        print(" | ".join(str(row[header]).ljust(widths[header]) for header in headers))


def _result_to_dict(result) -> dict[str, object]:
    return {
        **result.row(),
        "sections": result.context.section_labels(),
        "answer": result.generation.text,
    }
