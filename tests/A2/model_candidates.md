# Current Qwen model candidate check

Checked Hugging Face on 2026-10-09 before choosing the test model. The Qwen organization currently publishes Qwen3.8, including a 180B Flash-Next model that is too large for this node and the official `Qwen/Qwen3.8-27B-FP8` checkpoint as the compact current candidate. The node's Hugging Face metadata reported a total repository size of 28.77 GiB (commit `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`). Its config uses the `Qwen3_5ForCausalLM` architecture, implemented in vLLM 0.21.0. The checkpoint has now been tested on one A100: it starts at 65,536 tokens and passes the 60k prompt test.

The local setup cache also had a community `abihsoro/Qwen3.8-27B-AWQ-INT4` entry, but it only contained tokenizer/config assets (about 20 MiB) and no weights, so it was not launchable. The current reasoning-separation and cutoff tests continue on the cached Qwen3-30B-A3B-Thinking-2507-FP8 checkpoint because those tests require a thinking model.

Sources: [official Qwen model catalog](https://huggingface.co/Qwen/models), [Qwen3.8-27B model card](https://huggingface.co/Qwen/Qwen3.8-27B), [official Qwen3.8-27B-FP8 checkpoint](https://huggingface.co/Qwen/Qwen3.8-27B-FP8).
