# Failures

## Setup: llm-setup prerequisite (USER stop)

- Command: `git -C llm-setup log -1 --oneline; git ls-tree HEAD llm-setup; git -C llm-setup status --short --branch`
- Exit code: 0 (commands succeeded; required version check failed).
- Output (all lines):
  ```text
  891487d Add pinned subagent aliases and longer proxy timeout
  160000 commit b962edd83c987efd1275ee535dd19bc4186e4ce3 llm-setup
  ## main...origin/main
   M docs/OPERATIONS.md
   M slurm/llm-stack.sbatch
   M src/llm_setup/supervisor.py
  ```
- `docs/runbook-question-first.md` section 0 says to stop for USER if the submodule log shows a commit other than `4c8ccbf`. The current main gitlink itself points to `b962edd`, and the existing checkout has local changes. No submodule change or stack launch was attempted.

## Setup: dependency sync interrupted at USER stop

- Command: `uv sync --locked`
- Exit code: 130 (interrupted when the prerequisite USER stop was identified).
- Last output:
  ```text
  Resolved 233 packages in 213ms
     Building thesis-agent @ file:///mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent
  Downloading pdfminer-six (6.3MiB)
  Downloading pypdfium2 (3.6MiB)
        Built thesis-agent @ file:///mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent
   Downloaded pypdfium2
   Downloaded pdfminer-six
  Prepared 7 packages in 1.88s
  ```

Resolution: User confirmed `b962edd` for this run. The saved local diff changes shared stack startup files `slurm/llm-stack.sbatch` and `src/llm_setup/supervisor.py` (model startup and ports), which can affect orch/GLiNER stack operation; it does not directly edit an orch-3x40 profile or a GLiNER-named file. It is preserved at `$EV/llm-setup-local.diff` and in the llm-setup Git stash.

## Existing allocation: model-list check

- Command: `srun --jobid 8424 --overlap bash -c '... curl .../v1/models | python ...; nvidia-smi ...'` (the authorization header was supplied from the existing stack's `.env`).
- Exit code: 0 for the overall shell; the model-list pipeline failed because `python` was absent from the allocation's PATH and curl consequently reported a broken pipe. The following `nvidia-smi` masked the pipeline status.
- Output excerpt: `/usr/bin/bash: line 1: python: command not found`; `curl: Failed writing body`.
- Retried with `python3` and `pipefail`: exit 0, models include `orch-model`. GLiNER `/info` returned the pinned model and revision. Per user instruction, job 8563 was canceled and existing job 8424 is used.

## offline-pytest

- Command: `uv` `run` `pytest` `evidence` `synth` `evaluation` `modelcall` `webapp` `-q`
- Exit code: 1
- Last 30 log lines:
  ```text
                                     "extractors": "cascade", "strategy": "gaps"})
        agentic = start(client, "run", {"corpus": corpus, "protocol": {"source": "repo", "name": "rag-factuality-agentic"},
                                        "strategy": "gaps", "model": "other-model"})
        frozen = start(client, "run", {"corpus": corpus, "protocol": {"source": "proposal", "name": "rag-factuality"}})
        for job in (regex, gaps, agentic, frozen):
            assert wait(client, job["id"])["state"] == "done"
        assert (regex["lane"], gaps["lane"]) == ("cpu", "model")
>       assert [j["refs"]["run"] for j in (regex, gaps, agentic, frozen)] == [
            f"regex-only~{corpus}", f"cascade-gaps~{corpus}", f"agentic-gaps~{corpus}", f"proposal-rag-factuality-cascade~{corpus}"]
E       AssertionError: assert ['regex-only~...-paraphrased'] == ['regex-only~...-paraphrased']
E         
E         At index 3 diff: 'proposal-rag-factuality-cascade-gaps~rag-tpl-w1-paraphrased' != 'proposal-rag-factuality-cascade~rag-tpl-w1-paraphrased'
E         Use -v to get more diff

webapp/tests/test_evjobs.py:145: AssertionError
=============================== warnings summary ===============================
evidence/tests/test_open_types.py:157
  /mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent/evidence/tests/test_open_types.py:157: SyntaxWarning: invalid escape sequence '\['
    with pytest.raises(ValueError, match="several types of role 'compared_thing'.*\['arm', 'drug'\]"):

evaluation/tests/test_wholerun.py::test_refuses_tune_papers
  /mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent/evaluation/wholerun.py:259: UserWarning: q1: none of its paper ids is in /tmp/pytest-of-xepi3167/pytest-151/test_refuses_tune_papers0/tune_split.json; the tune guard cannot check it
    tuned = sorted(set(question_papers(q)) & tune_papers(q))

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED evaluation/tests/test_score_kinds.py::test_effect_scores_unchanged[pilot-complex]
FAILED evaluation/tests/test_score_kinds.py::test_effect_scores_unchanged[tpl-s1-mixed]
FAILED webapp/tests/test_evjobs.py::test_run_jobs_with_the_runbooks_groups - ...
3 failed, 2336 passed, 1 skipped, 2 warnings in 1561.38s (0:26:01)

  ```

## Dataset download: SciLead guessed URL
- The initial guessed URL `https://aclanthology.org/2024.emnlp-main.453.data.zip` returned HTTP 404; the subsequent archive listing failed because the file was absent.
- Retried using the ACL Anthology page's actual attachments link; download succeeded.

## Additional dataset downloads
- MuLMS repository archive URL guessed with branch `main` returned HTTP 404; retry with the repository's `master` branch succeeded.
- SuperCon repository archive URL guessed with branch `master` returned HTTP 404; retry with the repository's `main` branch succeeded.

## SciLead fetch stalled
- After the fetch environment installed successfully, `evidence fetch` remained blocked in a shared-storage read (`folio_wait_bit_common`) for over three minutes without creating a corpus or writing a log. The process had not exited at the time recorded; final status is pending.

## Section 3.5: PDF conversion not exercised
- The three requested IDs all fetched LaTeX sources successfully; none required PDF conversion. Therefore the runbook's real Docling PDF and table check remains unverified.
- The SciLead fetch resumed after the previously recorded shared-storage stall and completed with 31 papers and zero skipped among the arXiv IDs. Twelve source papers lacked arXiv IDs.

## Slurm step status query
- A diagnostic `squeue --steps` query used job-only format fields and printed invalid-format errors; it still showed the ReadClaim step 8424.5 running. The model run itself was unaffected.

## ReadClaim run
- Exit code: 1; see logs/readclaim.log and readclaim.launch.

## ReadClaim model failure details
- Slurm step 8424.5 exited 1 without aggregate scores. Last 30 log lines:

```text
                                     messages=call.messages, call_kwargs=call.kwargs)
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent/.venv/lib/python3.13/site-packages/dspy/clients/engines/legacy_engine.py", line 72, in complete_legacy
    raw = self.lm.forward(prompt=prompt, messages=messages, **(call_kwargs or {}))
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent/modelcall/dspy_lm.py", line 74, in forward
    if self._with_call else self._ask(render(msgs)))
                            ~~~~~~~~~^^^^^^^^^^^^^^
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent/evidence/stages.py", line 240, in ask
    return ask_sync(Prompt.inline("", Reply), text, model=openai_model(alias)).output.text
           ~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent/modelcall/call.py", line 168, in ask_sync
    return run_sync(ask(prompt, user_prompt, model=model, settings=settings, cache=cache, key=key,
                        refresh=refresh, extra=extra, timeout_s=timeout_s))
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent/modelcall/loop.py", line 44, in run_sync
    return asyncio.run_coroutine_threadsafe(coro, loop).result()
           ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/.local/share/uv/python/cpython-3.13.12-linux-x86_64-gnu/lib/python3.13/concurrent/futures/_base.py", line 456, in result
    return self.__get_result()
           ~~~~~~~~~~~~~~~~~^^
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/.local/share/uv/python/cpython-3.13.12-linux-x86_64-gnu/lib/python3.13/concurrent/futures/_base.py", line 401, in __get_result
    raise self._exception
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent/modelcall/call.py", line 154, in ask
    reply, messages = await on_model_loop(_attempt(prompt, user_prompt, model, settings, timeout_s))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent/modelcall/loop.py", line 51, in on_model_loop
    return await coro
           ^^^^^^^^^^
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent/modelcall/call.py", line 129, in _attempt
    raise err from None
modelcall.call.ModelCallError: UnexpectedModelBehavior: Exceeded maximum output retries (1)
srun: error: gammaweb08: task 0: Exited with exit code 1

```

## ReadClaim retry
- Exit code: 1. Last 30 log lines:

```text
                                     messages=call.messages, call_kwargs=call.kwargs)
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent/.venv/lib/python3.13/site-packages/dspy/clients/engines/legacy_engine.py", line 72, in complete_legacy
    raw = self.lm.forward(prompt=prompt, messages=messages, **(call_kwargs or {}))
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent/modelcall/dspy_lm.py", line 74, in forward
    if self._with_call else self._ask(render(msgs)))
                            ~~~~~~~~~^^^^^^^^^^^^^^
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent/evidence/stages.py", line 240, in ask
    return ask_sync(Prompt.inline("", Reply), text, model=openai_model(alias)).output.text
           ~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent/modelcall/call.py", line 168, in ask_sync
    return run_sync(ask(prompt, user_prompt, model=model, settings=settings, cache=cache, key=key,
                        refresh=refresh, extra=extra, timeout_s=timeout_s))
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent/modelcall/loop.py", line 44, in run_sync
    return asyncio.run_coroutine_threadsafe(coro, loop).result()
           ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/.local/share/uv/python/cpython-3.13.12-linux-x86_64-gnu/lib/python3.13/concurrent/futures/_base.py", line 456, in result
    return self.__get_result()
           ~~~~~~~~~~~~~~~~~^^
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/.local/share/uv/python/cpython-3.13.12-linux-x86_64-gnu/lib/python3.13/concurrent/futures/_base.py", line 401, in __get_result
    raise self._exception
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent/modelcall/call.py", line 154, in ask
    reply, messages = await on_model_loop(_attempt(prompt, user_prompt, model, settings, timeout_s))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent/modelcall/loop.py", line 51, in on_model_loop
    return await coro
           ^^^^^^^^^^
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent/modelcall/call.py", line 129, in _attempt
    raise err from None
modelcall.call.ModelCallError: UnexpectedModelBehavior: Exceeded maximum output retries (1)
srun: error: gammaweb08: task 0: Exited with exit code 1

```

## Single-sentence ReadClaim diagnostic
- Exit code: 1; see debug/readclaim-probe.log. Last 30 lines:

```text
                                     messages=call.messages, call_kwargs=call.kwargs)
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent/.venv/lib/python3.13/site-packages/dspy/clients/engines/legacy_engine.py", line 72, in complete_legacy
    raw = self.lm.forward(prompt=prompt, messages=messages, **(call_kwargs or {}))
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent/modelcall/dspy_lm.py", line 74, in forward
    if self._with_call else self._ask(render(msgs)))
                            ~~~~~~~~~^^^^^^^^^^^^^^
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent/evidence/stages.py", line 240, in ask
    return ask_sync(Prompt.inline("", Reply), text, model=openai_model(alias)).output.text
           ~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent/modelcall/call.py", line 168, in ask_sync
    return run_sync(ask(prompt, user_prompt, model=model, settings=settings, cache=cache, key=key,
                        refresh=refresh, extra=extra, timeout_s=timeout_s))
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent/modelcall/loop.py", line 44, in run_sync
    return asyncio.run_coroutine_threadsafe(coro, loop).result()
           ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/.local/share/uv/python/cpython-3.13.12-linux-x86_64-gnu/lib/python3.13/concurrent/futures/_base.py", line 456, in result
    return self.__get_result()
           ~~~~~~~~~~~~~~~~~^^
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/.local/share/uv/python/cpython-3.13.12-linux-x86_64-gnu/lib/python3.13/concurrent/futures/_base.py", line 401, in __get_result
    raise self._exception
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent/modelcall/call.py", line 154, in ask
    reply, messages = await on_model_loop(_attempt(prompt, user_prompt, model, settings, timeout_s))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent/modelcall/loop.py", line 51, in on_model_loop
    return await coro
           ^^^^^^^^^^
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent/modelcall/call.py", line 129, in _attempt
    raise err from None
modelcall.call.ModelCallError: UnexpectedModelBehavior: Exceeded maximum output retries (1)
srun: error: gammaweb08: task 0: Exited with exit code 1

```

## ReadClaim prompt capture
- Exit code 1 resulted from an intentional interception after successfully capturing the request; no model request was sent during capture.
```text
                                     messages=call.messages, call_kwargs=call.kwargs)
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent/.venv/lib/python3.13/site-packages/dspy/clients/engines/legacy_engine.py", line 72, in complete_legacy
    raw = self.lm.forward(prompt=prompt, messages=messages, **(call_kwargs or {}))
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent/modelcall/dspy_lm.py", line 74, in forward
    if self._with_call else self._ask(render(msgs)))
                            ~~~~~~~~~^^^^^^^^^^^^^^
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent/evidence/stages.py", line 240, in ask
    return ask_sync(Prompt.inline("", Reply), text, model=openai_model(alias)).output.text
           ~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent/modelcall/call.py", line 168, in ask_sync
    return run_sync(ask(prompt, user_prompt, model=model, settings=settings, cache=cache, key=key,
                        refresh=refresh, extra=extra, timeout_s=timeout_s))
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent/modelcall/loop.py", line 44, in run_sync
    return asyncio.run_coroutine_threadsafe(coro, loop).result()
           ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/.local/share/uv/python/cpython-3.13.12-linux-x86_64-gnu/lib/python3.13/concurrent/futures/_base.py", line 456, in result
    return self.__get_result()
           ~~~~~~~~~~~~~~~~~^^
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/.local/share/uv/python/cpython-3.13.12-linux-x86_64-gnu/lib/python3.13/concurrent/futures/_base.py", line 401, in __get_result
    raise self._exception
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent/modelcall/call.py", line 154, in ask
    reply, messages = await on_model_loop(_attempt(prompt, user_prompt, model, settings, timeout_s))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent/modelcall/loop.py", line 51, in on_model_loop
    return await coro
           ^^^^^^^^^^
  File "/mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-research-agent/modelcall/call.py", line 129, in _attempt
    raise err from None
modelcall.call.ModelCallError: Captured: 
srun: error: gammaweb08: task 0: Exited with exit code 1

```

## Plain-text gateway targeted tests
- Exit code 1.
```text
        def reply(messages, info):
            asked.append("x")
            return respond(info, {"text": "not json at all" if len(asked) == 1 else '{"echo": "ok"}'})
    
        def stage(run, ctx):
            steps.configure(ctx.dspy_lm("demo-step"))
            try:
                return {"echo": steps.Step(EchoSig, "echo")(text="hi").echo}
            finally:
                steps._LM = None
    
        stages.register("stp", "after_run", stage)
        root = _run(tmp_path, provider=provider_of(FunctionModel(reply, model_name="echo")))
>       assert json.loads((root / "stp.json").read_text(encoding="utf-8")) == {"echo": "ok"}
E       assert {'failed': 'A...nse: [] \n\n'} == {'echo': 'ok'}
E         
E         Left contains 1 more item:
E         {'failed': 'AdapterParseError: Adapter JSONAdapter failed to parse the LM '
E                    'response. \n'
E                    '\n'
E                    'LM Response: {"text": "{\\"echo\\": \\"ok\\"}"} \n'
E                    '\n'...
E         
E         ...Full output truncated (7 lines hidden), use '-vv' to show

evidence/tests/test_stages.py:288: AssertionError
=========================== short test summary info ============================
FAILED evidence/tests/test_stages.py::test_a_stage_gets_a_recorded_dspy_lm - ...
FAILED evidence/tests/test_stages.py::test_a_step_with_a_bad_first_reply_succeeds_on_attempt_1_and_replays_without_calls
2 failed, 53 passed in 74.78s (0:01:14)

```

## Plain-text gateway targeted test retry
- Exit code 1.
```text
..................................................F....                  [100%]
=================================== FAILURES ===================================
____ test_a_stage_model_call_is_logged_counted_and_replays_without_a_model _____

tmp_path = PosixPath('/tmp/pytest-of-xepi3167/pytest-154/test_a_stage_model_call_is_log0')

    def test_a_stage_model_call_is_logged_counted_and_replays_without_a_model(tmp_path: Path) -> None:
        base = _run(tmp_path / "base", provider=None)
        stages.register("echo", "after_run", _ask_stage())
        root = _run(tmp_path / "with", provider=_provider())
>       assert json.loads((root / "echo.json").read_text(encoding="utf-8")) == {"answer": "hi there"}
E       AssertionError: assert {'failed': 'S... retries (1)'} == {'answer': 'hi there'}
E         
E         Left contains 1 more item:
E         {'failed': 'StageCallError: demo-echo: UnexpectedModelBehavior: Exceeded '
E                    'maximum output retries (1)'}
E         Right contains 1 more item:
E         {'answer': 'hi there'}
E         Use -v to get more diff

evidence/tests/test_stages.py:219: AssertionError
=========================== short test summary info ============================
FAILED evidence/tests/test_stages.py::test_a_stage_model_call_is_logged_counted_and_replays_without_a_model
1 failed, 54 passed in 72.63s (0:01:12)

```

## Push of SciLead planning artifacts
- Initial push failed with `Permission denied (publickey)`; GitHub SSH authentication did not accept the current credentials. The planning artifacts remain committed locally.
- The second SSH push failed with the same public-key error; retrying with the existing authenticated GitHub CLI credential helper over HTTPS.
- HTTPS push using the authenticated GitHub CLI credential also failed: HTTP 403, write access not granted. Local commits are retained.

- 2026-11-04: Diagnostic `squeue --steps` used unsupported format specifier `%T`; Slurm rejected that column. The job-step listing still showed step 8424.15 running. No evaluation was affected.

- 2026-11-04: Offline pytest after plain-text fix: 17 failed, 2323 passed, 1 skipped. This includes the 3 previously known failures and 14 additional failures; full details in logs/offline-pytest-plain-fix.log. Investigation pending.

- 2026-11-04: SOFC converter inspection command used `python`, which is unavailable on this host; retrying with `python3`. Conversion itself succeeded.

- 2026-11-04 MeasEval inspection: `python` was unavailable on PATH (exit 127); retried with `python3`. Conversion had already succeeded with `uv run`.
- 2026-11-04: Initial SOFC conversion incorrectly treated text file line breaks as sentence boundaries. Hand-checking PMC3793895 showed empty/misaligned spans. Corrected converter uses the release's sentence offset files; initial output preserved as sofc-initial-incorrect-offsets.json and corrected output saved as sofc.json. No evaluations used the initial output.

- 2026-11-04: Focused plan-run fixture check: 34 passed, 1 failed (`test_old_protocol_lock_unchanged`). The 13 previously failing plan-run tests now pass after fixing their fake text replies. The remaining lock mismatch is due to LLM extractor source fingerprints including the changed `modelcall/call.py`; see logs/plan-run-fixtures-check.log and logs/protocol-lock-diff.txt. Historical compatibility remains unresolved.
- 2026-11-04: Status command returned exit 2 because launch completion files were not yet present while both steps were running; no evaluation failure was established.
- 2026-11-04: Independent SOFC converter review found that 352 of 1,032 frames have repeated slots; converting these to joined strings does not faithfully match the existing experiment scorer's one-setting-value matching. SOFC frame scores must not be interpreted until reviewed. No SOFC evaluation was run.
- 2026-11-04: Adding the completed SciLead run folders failed because reports/general/runs is gitignored; retrying with explicit force-add, as the user requested these run folders on the branch. No data was removed.
- SciLead full-set scilead-02 reasoning-on answer records OpenAlex link resolution failures including HTTP 429 and unreachable service; affected links are marked outside the set. See runs/full/scilead/auto-confirmed/on/scilead-02/answer.json.
- SciLead full-set scilead-07 reasoning-on stage_report records an unchecked experiment map for paper 1912.08777v3 due to model HTTP 400 context window exceeded. See runs/full/scilead/auto-confirmed/on/scilead-07/stage_report.json.
- 2026-11-04: Monitoring the reasoning-off launcher through its old process handle failed because the handle was unavailable after an interrupted wait; checking the Slurm step and launch log instead.
- 2026-11-04: The reasoning-on launcher process handle was also unavailable after the interrupted wait; Slurm still lists both evaluation steps. Monitoring their launch logs instead.
- 2026-11-04: Both full SciLead row launcher processes disappeared after monitoring handles became unavailable, without launch completion records. At detection reasoning-on had 21 answer files and off had 22; the last runs may be unsealed. Resuming each row with existing caches; runner preserves unsealed folders as failed siblings.
- 2026-11-04: A detached launcher attempt did not persist in this execution environment and produced no step logs. Restarted both rows through monitored sessions.
- 2026-11-04: Full SciLead wholerun answer-key split failed for scilead-05 and scilead-06 in both reasoning rows: ValueError missing parameter(s) ['metric']; despite merged runtime query fix. Headline scores were produced, but split attribution for these items is unavailable. See scores/full/scilead/wholerun.md.
- 2026-11-04: Artifact review checked `git lfs version`; Git LFS is not installed (exit 1). Existing Git push remains available; no storage migration was attempted.
- 2026-11-04: Full SciLead artifact audit: each of 22 questions in each reasoning row has at least one ContextWindowExceededError in stage_report.json and at least one resolve_failed link in answer.json; 2 questions per row have a non-done evidence line. These are counts of affected questions, not failed calls; details remain in each run folder.
- 2026-11-04: Improvement-review inspection referenced nonexistent evidence/costs.py; rg/sed reported file-not-found. Read-only review continued using existing files.
- 2026-11-04: Full SciREX wholerun reports all 15 engine questions unscored in each reasoning row (displayed headline mean 0.000 must not be treated as valid accuracy); 77 of 270 relations are left out because the document is absent. RAG rows also report 1 global and 3 per-paper unscored. See scores/full/scirex/wholerun.md; cause needs investigation.
- 2026-11-04: SciREX review inspection referenced nonexistent evidence/kg/templates.py; read-only rg failed and review continued using actual template files.
- 2026-11-04: All 15 first-line SciREX plans query kg:dataset, absent from their generated graphs; read-only probe replacing that predicate with ev:setting_dataset returned rows for scirex-001. This explains empty engine lists; original artifacts and scores are retained.
- 2026-11-04: Fixed SciREX reruns were launched with the tested query.py change present in the working tree just before committing it as b713dea8. Early run manifests may record the prior HEAD; the executed query compatibility code is commit b713dea8. Inspect per-run manifests before replay or attribution.
- 2026-11-04: After the saved-query compatibility fix, SciREX wholerun still marks 11 of 15 engine questions unscored in each row, and 1 global/3 per-paper baseline questions unscored; 77 of 270 relations lack corpus documents. Reported headline means include zero contributions for empty predictions; consult scores/fixed/scirex/wholerun.md and unscored counts.
2026-11-04T17:50:26+01:00: leak score rag-claude-s1-mixed exit 1
2026-11-04T17:54:07+01:00: synthetic engine rag-claude-s1-paraphrased exit 2
2026-11-04T17:55:05+01:00: leak score rag-claude-s1-distributed exit 1
2026-11-04T17:59:41+01:00: leak score rag-claude-s1-complex exit 1
2026-11-04T18:05:55+01:00: synthetic engine rag-claude-s1-complex exit 2
- 2026-11-04: Off-template questions q06 and q10 failed protocol validation because treatment and control both resolved to role `other`; their folders are absent and the run exited 1. See logs/runs-offtemplate.log.
- 2026-11-04: Leak scoring failed on the mixed, distributed and complex corpora because `evaluate leak` rejects evidence_type `experiment` (not registered by the validator). Runs are preserved; see logs/leak-score.log.
2026-11-04T18:27:50+01:00: synthetic engine rag-claude-s1-paraphrased exit 2
2026-11-04T18:28:24+01:00: synthetic engine rag-claude-s1-complex exit 2
- 2026-11-04: Final artifact copy attempted reports/general/scores/leak before the path existed; cp returned cannot stat. Leak scoring errors are recorded, and no leak score directory was produced.
- 2026-11-04: Git artifact staging included reports/general/scores/leak, which does not exist because all leak evaluations failed before producing score files. Git rejected that pathspec; retrying with only existing artifact paths.
- 2026-11-04: Final offline suite: 2344 passed, 4 failed, 1 skipped in 1523.44s. Three are known baseline failures (two score golden token differences and runbook job-group naming); the fourth is test_old_protocol_lock_unchanged caused by changed extractor fingerprint. See reports/general/logs/offline-final.log.
