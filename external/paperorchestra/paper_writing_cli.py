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

# Thesis adaptation (VENDORED.md): Markdown pipeline with the Claude Code backend. Plotting, LaTeX templates,
# research cutoff and the separate reflection/plotting/image models are gone (no figures, no literature search,
# one Claude model for every agent).

import argparse
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def main():
    parser = argparse.ArgumentParser(
        description="CLI for generating a single paper (Markdown) from the Paper Orchestra pipeline."
    )
    parser.add_argument("--raw_materials_dir", required=True,
                        help="Directory containing idea_sparse.md and experimental_log.md.")
    parser.add_argument("--output_dir", required=True, help="Work directory for this paper.")
    parser.add_argument("--template_dir", default=os.path.join(HERE, "templates", "markdown"),
                        help="Directory with template.md and guidelines.md.")
    parser.add_argument("--idea_filename", default="idea_sparse.md")
    parser.add_argument("--experimental_log_filename", default="experimental_log.md")
    parser.add_argument("--writer_model_name", default="claude-haiku-5-5", help="Claude model for every agent.")
    parser.add_argument("--cache_dir", required=True, help="On-disk LLM call cache (keyed by prompt hash).")
    parser.add_argument("--lock_dir", required=True, help="Folder of the 3 shared slot locks (parallel cap).")
    parser.add_argument("--log_path", required=True, help="JSONL log of calls, checks and repairs.")
    parser.add_argument("--max_reflections", type=int, default=1)
    parser.add_argument("--num_review_ensemble", type=int, default=1)
    parser.add_argument("--prompt_version", default="v1", help="Writer prompt set: v1 (default) or v2 (C7).")
    parser.add_argument("--style_examples", default=None,
                        help="JSON file of style examples [{id, about, license, sections}] (needed by v2).")
    parser.add_argument("--references", default=None,
                        help="JSON file of references [{id, first_author, authors_text, year, venue, title, gist, "
                             "abstract}] (v2r, C8).")
    parser.add_argument("--timeout", type=int, default=900, help="Seconds per claude call.")
    parser.add_argument("--backend_json", default=None,
                        help="C9: paperfactory RoleModel fields as JSON; every call then goes through paperfactory's "
                             "model layer (run in the main project environment).")
    parser.add_argument("--max_parallel", type=int, default=3, help="Slot locks in --lock_dir (at most 3).")
    args = parser.parse_args()

    from utils.claude_code_utils import ClaudeCodeLM
    from methods.paper_writer import write_single_paper

    if not os.path.exists(args.raw_materials_dir):
        print(f"Error: Raw materials directory '{args.raw_materials_dir}' does not exist.")
        sys.exit(1)
    base_dir = args.output_dir
    os.makedirs(base_dir, exist_ok=True)
    target_raw_materials = os.path.join(base_dir, "raw_materials")
    os.makedirs(target_raw_materials, exist_ok=True)
    for name in (args.idea_filename, args.experimental_log_filename):
        shutil.copy(os.path.join(args.raw_materials_dir, name), os.path.join(target_raw_materials, name))

    runner, label = None, args.writer_model_name
    if args.backend_json:
        from paperfactory.llm import po_runner
        runner, label = po_runner(json.loads(args.backend_json))
    lm = ClaudeCodeLM(label, cache_dir=args.cache_dir, lock_dir=args.lock_dir, log_path=args.log_path,
                      timeout=args.timeout, max_parallel=args.max_parallel, runner=runner)
    print(f"Starting Paper Generation (Markdown) in {base_dir}")
    summary = write_single_paper(
        base_dir=base_dir,
        lm=lm,
        template_dir=args.template_dir,
        idea_filename=args.idea_filename,
        experimental_log_filename=args.experimental_log_filename,
        max_reflections=args.max_reflections,
        num_review_ensemble=args.num_review_ensemble,
        prompt_version=args.prompt_version,
        style_examples=json.load(open(args.style_examples, encoding="utf-8")) if args.style_examples else None,
        references=json.load(open(args.references, encoding="utf-8")) if args.references else None,
    )
    print("SUMMARY " + json.dumps(summary))


if __name__ == "__main__":
    main()
