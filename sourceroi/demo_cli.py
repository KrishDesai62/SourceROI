"""SourceROI command line entrypoint."""
from __future__ import annotations
import argparse
import json
import sys
from .corpus import load_project
from .evaluation import ablation_study, change_report, evaluate, optimize_portfolio
from .store import read_baseline, save_baseline


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="SourceROI: test which data helps your AI agent")
    parser.add_argument("--project", default=None, help="Path to directory containing project.json")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="Launch dashboard (no dependencies)")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    eva = sub.add_parser("evaluate", help="Run baseline or counterfactual evaluation")
    eva.add_argument("--without", nargs="*", default=[], metavar="SOURCE_ID")
    eva.add_argument("--json", action="store_true", dest="as_json")
    sub.add_parser("ablate", help="Rank sources and documents by benchmark impact")
    sub.add_parser("optimize", help="Best benchmark source sets at 75%, 85%, 95% and 100% accuracy")
    sub.add_parser("save-baseline", help="Save current data and evaluation as baseline")
    sub.add_parser("compare", help="Compare current files to saved baseline")
    args = parser.parse_args(argv)
    try:
        project = load_project(args.project)
        if args.command == "serve":
            from .service import serve as runserver
            runserver(args.host, args.port, args.project)
            return 0
        if args.command == "evaluate":
            valid = {s["id"] for s in project["sources"]}
            unknown = set(args.without) - valid
            if unknown:
                parser.error("Unknown source IDs: " + ", ".join(sorted(unknown)))
            report = evaluate(project, exclude_sources=set(args.without))
            if args.as_json:
                print(json.dumps(report, indent=2))
            else:
                m = report["metrics"]
                print(f"{project['name']}: {m['passed']}/{m['task_count']} correct ({m['accuracy']:.1%})")
                print(f"Modeled data lookup cost: ${m['estimated_total_source_cost_usd']:.4f}")
                print(f"Modeled source latency: {m['mean_modeled_source_latency_ms']:.1f} ms/task")
                for t in report["tasks"]:
                    print(f"  {'PASS' if t['correct'] else 'FAIL'}  {t['id']}  {t['question']} -> {t['actual']}")
            return 0
        if args.command == "ablate":
            study = ablation_study(project)
            for row in study["sources"]:
                print(f"{row['source_name']:<25} -{len(row['lost_tasks']):>2} passed tasks | modeled savings ${row['saved_cost_usd']:.4f}")
            print("\nHighest impact documents:")
            for row in study["documents"][:10]:
                print(f"{len(row['lost_tasks']):>2} lost tasks | {row['title']}")
            return 0
        if args.command == "optimize":
            for floor in (.75, .85, .95, 1.0):
                result = optimize_portfolio(project, floor)
                best = result["best"]
                if best:
                    print(f"Quality floor {floor:.0%}: {best['accuracy']:.1%} accurate, "
                          f"${best['cost_usd']:.4f} modeled lookup cost, "
                          f"{', '.join(best['source_ids']) or '(no sources)'}")
            return 0
        if args.command == "save-baseline":
            report = evaluate(project)
            print("Saved:", save_baseline(project, report))
            return 0
        if args.command == "compare":
            saved = read_baseline(project)
            if not saved:
                print("No baseline saved. Run: python -m sourceroi save-baseline", file=sys.stderr)
                return 1
            report = change_report(saved, evaluate(project), project)
            print(json.dumps(report, indent=2))
            return 0
        return 1
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"SourceROI error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
