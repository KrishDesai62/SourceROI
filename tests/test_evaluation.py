"""Tests for observable behavior, ablations, leakage boundary and Data CI."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from sourceroi.agents import ABSTAIN, answer
from sourceroi.corpus import DEFAULT_PROJECT, load_project
from sourceroi.evaluation import ablation_study, change_report, differences, evaluate, optimize_portfolio
from sourceroi.store import read_baseline, save_baseline


class SourceROITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.project = load_project()

    def test_all_demo_questions_pass_with_full_corpus(self):
        report = evaluate(self.project)
        self.assertEqual(report["metrics"]["task_count"], 22)
        self.assertEqual(report["metrics"]["passed"], 22)
        self.assertEqual(report["metrics"]["accuracy"], 1.0)

    def test_question_only_cannot_get_answer_without_sources(self):
        result = answer("What was Aster Robotics' FY2025 revenue?", [])
        self.assertEqual(result["answer"], ABSTAIN)

    def test_no_benchmark_ground_truth_is_provided_to_agent(self):
        question = self.project["benchmark"][0]["question"]
        docs = self.project["documents"]
        result = answer(question, docs)
        self.assertEqual(result["answer"], "$980 million")
        # The answering API accepts only the question and documents, never expected.
        self.assertNotIn("expected", result)

    def test_fiscal_year_sensitivity(self):
        by_id = {t["id"]: t for t in evaluate(self.project)["tasks"]}
        self.assertEqual(by_id["F01"]["actual"], "$980 million")
        self.assertEqual(by_id["F04"]["actual"], "$810 million")
        self.assertEqual(by_id["F09"]["actual"], "$135 million")

    def test_source_ablation_finds_lost_tasks(self):
        all_report = evaluate(self.project)
        cut_report = evaluate(self.project, exclude_sources={"alternative"})
        delta = differences(all_report, cut_report)
        self.assertEqual(set(delta["lost_task_ids"]), {"A01", "A02", "A03"})
        self.assertEqual(cut_report["metrics"]["passed"], 19)
        self.assertLess(cut_report["metrics"]["estimated_total_source_cost_usd"],
                        all_report["metrics"]["estimated_total_source_cost_usd"])

    def test_individual_document_ablation(self):
        result = evaluate(self.project, exclude_documents={"filings::aster_fy2025.md"})
        lost = differences(evaluate(self.project), result)["lost_task_ids"]
        self.assertTrue({"F01", "F02", "F03"}.issubset(set(lost)))

    def test_fact_ablation_identifies_crucial_information(self):
        result = evaluate(self.project, exclude_facts={"filings::aster_fy2025.md": {"revenue"}})
        self.assertIn("F01", differences(evaluate(self.project), result)["lost_task_ids"])

    def test_optimizer_finds_lowest_cost_with_quality_floor(self):
        result = optimize_portfolio(self.project, .85)
        self.assertEqual(result["configurations_tested"], 32)
        self.assertGreaterEqual(result["best"]["accuracy"], .85)
        self.assertNotIn("alternative", result["best"]["source_ids"])
        full = evaluate(self.project)["metrics"]["estimated_total_source_cost_usd"]
        self.assertLess(result["best"]["cost_usd"], full)

    def test_study_ranks_documents_and_sources(self):
        results = ablation_study(self.project)
        self.assertEqual(len(results["sources"]), 5)
        self.assertEqual(len(results["documents"]), 17)
        self.assertGreater(len(results["facts"]), 20)
        self.assertGreaterEqual(len(results["documents"][0]["lost_tasks"]), 1)

    def test_changed_fact_is_detected_and_regresses_task(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "finance"
            shutil.copytree(DEFAULT_PROJECT, root)
            project = load_project(root)
            old = evaluate(project)
            save_baseline(project, old)
            doc = root / "sources" / "filings" / "aster_fy2025.md"
            doc.write_text(doc.read_text().replace("Revenue: $980 million", "Revenue: $900 million"))
            changed = load_project(root)
            report = change_report(read_baseline(changed), evaluate(changed), changed)
            self.assertIn("F01", report["diff"]["lost_task_ids"])
            self.assertIn("filings::aster_fy2025.md", report["files_changed"])

    def test_source_cost_and_latency_are_explicitly_modeled(self):
        first = evaluate(self.project)["tasks"][0]
        self.assertGreater(first["source_lookup_cost_usd"], 0)
        self.assertGreater(first["modeled_latency_ms"], 0)
        self.assertGreaterEqual(first["local_compute_ms"], 0)
        self.assertNotIn("llm_cost_usd", first)

    def test_invalid_source_price_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "finance"
            shutil.copytree(DEFAULT_PROJECT, root)
            path = root / "project.json"
            cfg = json.loads(path.read_text())
            cfg["sources"][0]["price_per_query_usd"] = -1
            path.write_text(json.dumps(cfg))
            with self.assertRaises(ValueError):
                load_project(root)


if __name__ == "__main__":
    unittest.main()
