# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Thesis adaptation (VENDORED.md, C1-C5): Claude Code backend; Markdown instead of LaTeX/PDF (no compile, no page
# screenshots, no VLM formatting loop); reviewer = the upstream AgentReview persona with a JSON schema; same
# accept/revert rule on review scores as upstream, plus a value gate: a revision that loses checked values is
# rejected. Defaults lowered for cost: 1 reviewer (upstream 3 + meta review), 1 reflection (upstream 3).

import os
import json
import statistics
from concurrent.futures import ThreadPoolExecutor

from autoraters.agent_review import get_agentreview_system_prompt
from utils.fact_check import check_facts

from methods.prompts.content_refinement_agent import (
    content_refinement_agent_system_prompt,
    content_refinement_schema,
    review_instructions,
    review_schema,
)

AXES = ["Originality", "Quality", "Clarity", "Significance", "Soundness", "Presentation", "Contribution",
        "Overall", "Confidence"]


class ContentRefinementAgent:
    def __init__(self, lm, experimental_log_md: str, guidelines_md: str, facts: list, work_dir: str,
                 max_reflections: int = 1, num_review_ensemble: int = 1,
                 system_prompt: str = content_refinement_agent_system_prompt):
        """
        Agent responsible for refining a paper by generating reviews and addressing feedback in a loop.
        """
        self.lm = lm
        self.max_reflections = max_reflections
        self.num_review_ensemble = num_review_ensemble
        self.system_prompt = system_prompt  # C7: v1 or v2 prompt set
        self.work_dir = work_dir
        os.makedirs(os.path.join(self.work_dir, "peer_reviews"), exist_ok=True)
        self.experimental_log_md = experimental_log_md
        self.guidelines_md = guidelines_md
        self.facts = facts
        self.worklogs = {}
        self.current_md = ""
        self.initial_score = 0
        self.current_score = 0

    def _write(self, name: str, text: str) -> None:
        with open(os.path.join(self.work_dir, name), "w", encoding="utf-8") as f:
            f.write(text)

    def _get_peer_review(self, paper_md: str, iteration_label: str):
        system = get_agentreview_system_prompt(is_knowledgeable=True, is_responsible=True, is_benign=True)
        user = review_instructions + "\nHere is the paper you are asked to review:\n```\n" + paper_md + "\n```"

        def one(i):
            return self.lm(system, user + ("" if i == 0 else f"\n(Independent review {i + 1}.)"), review_schema,
                           step=f"review_{iteration_label}")

        with ThreadPoolExecutor(max_workers=min(3, self.num_review_ensemble)) as pool:
            reviews = list(pool.map(one, range(self.num_review_ensemble)))
        review = dict(reviews[0])
        if len(reviews) > 1:  # upstream averages the integer scores of the ensemble (its meta review is skipped)
            for axis in AXES:
                review[axis] = int(round(statistics.mean(r[axis] for r in reviews)))
        self._write(os.path.join("peer_reviews", f"review_{iteration_label}.json"), json.dumps(review, indent=4))
        print(f" >> [Reviewer] Score for {iteration_label}: {review.get('Overall')}/10")
        return review, float(review.get("Overall", 0))

    def _extract_scores(self, review: dict) -> dict:
        scores = {}
        for axis in AXES:
            try:
                scores[axis] = float(review.get(axis, 0))
            except (TypeError, ValueError):
                scores[axis] = 0.0
        return scores

    def _n_failed(self, md: str) -> int:
        return sum(not r["ok"] for r in check_facts(md, self.facts))

    def run(self, paper_md: str) -> str:
        """
        1. Review the draft. 2. Refine -> review. 3. Keep the revision if the score rose (or stayed with sub-axes
        not worse, as upstream) AND it does not lose values. Repeat up to max_reflections. Returns the paper.
        """
        self.current_md = paper_md
        self._write("initial_draft.md", paper_md)
        current_review, self.current_score = self._get_peer_review(paper_md, "v0")
        self.initial_score = self.current_score

        for i in range(self.max_reflections):
            print(f"\n=== Refinement Iteration {i + 1}/{self.max_reflections} ===")
            previous_log_str = json.dumps(self.worklogs, indent=4) if self.worklogs else "None"
            user_prompt_text = f"""
REFLECTION ITERATION {i + 1}.

--- PREVIOUS ITERATION LOG ---
{previous_log_str}

--- CURRENT REVIEWER FEEDBACK (Score: {self.current_score}) ---
{json.dumps(current_review, indent=2)}

--- GUIDELINES ---
{self.guidelines_md}

--- EXPERIMENTAL LOG (Data Truth) ---
{self.experimental_log_md}

--- CURRENT PAPER (paper.md) ---
{self.current_md}

INSTRUCTION:
1. Your goal is to IMPROVE the reviewer score (Current: {self.current_score}).
2. Address the 'Weaknesses' and 'Questions' in the Reviewer Feedback above, within the materials.
3. Keep every value of the experimental log exactly where it is.
4. Return the worklog and the full revised Markdown paper.
"""
            try:
                parsed = self.lm(self.system_prompt, user_prompt_text, content_refinement_schema,
                                 step=f"refine_v{i + 1}")
            except Exception as e:
                print(f" >> Error during refinement call: {e}")
                break
            new_md = parsed["markdown"].strip() + "\n"
            self._write(f"refined_paper_v{i + 1}.md", new_md)
            new_review, new_score = self._get_peer_review(new_md, f"v{i + 1}")

            old_metrics = self._extract_scores(current_review)
            new_metrics = self._extract_scores(new_review)
            comparison_axes = [k for k in new_metrics if k not in ("Overall", "Confidence")]
            deltas = {k: new_metrics[k] - old_metrics[k] for k in comparison_axes}
            total_gain = sum(d for d in deltas.values() if d > 0)
            total_drop = sum(-d for d in deltas.values() if d < 0)
            failed_before, failed_after = self._n_failed(self.current_md), self._n_failed(new_md)
            entry = {"round": i + 1, "agent_plan": parsed["worklog"], "scores_before": old_metrics,
                     "scores_after": new_metrics, "deltas": deltas, "total_gain": total_gain,
                     "total_drop": total_drop, "values_failed_before": failed_before,
                     "values_failed_after": failed_after}

            if failed_after > failed_before:
                entry["outcome"] = "REJECTED_LOST_VALUES"        # thesis addition
            elif new_metrics["Overall"] > old_metrics["Overall"]:
                entry["outcome"] = "ACCEPTED_SCORE_INCREASE"
            elif new_metrics["Overall"] < old_metrics["Overall"]:
                entry["outcome"] = "REJECTED_SCORE_DECREASE"
            elif total_drop > total_gain:
                entry["outcome"] = "REJECTED_DEGRADATION"
            else:
                entry["outcome"] = "ACCEPTED_NEUTRAL_IMPROVEMENT"
            self.worklogs[f"v{i + 1}"] = entry
            self._write("content_refinement_worklog.json", json.dumps(self.worklogs, indent=4))
            print(f" >> v{i + 1}: {entry['outcome']} (Overall {old_metrics['Overall']} -> {new_metrics['Overall']},"
                  f" failed values {failed_before} -> {failed_after})")
            if entry["outcome"].startswith("ACCEPTED"):
                self.current_md, self.current_score, current_review = new_md, new_score, new_review
            else:
                break

        self._write("final_refined_paper.md", self.current_md)
        return self.current_md
