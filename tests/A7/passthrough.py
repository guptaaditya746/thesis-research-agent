from __future__ import annotations
import argparse
import json
import os
import time
from pathlib import Path
from openai import OpenAI

# The same request goes to vLLM directly and through LiteLLM, once with thinking off and once on.
# enable_thinking reaches vLLM through the proxy only if "off" has no reasoning and "on" has some.
p = argparse.ArgumentParser()
p.add_argument('--direct-url', default='http://127.0.0.1:8002/v1')
p.add_argument('--direct-model', default='heavy-model', help='served model name on the vLLM port')
p.add_argument('--proxy-url', default='http://127.0.0.1:4000/v1')
p.add_argument('--proxy-model', default='heavy-model', help='LiteLLM alias')
p.add_argument('--out', default='tests/A7/result.json')
a = p.parse_args()

direct = OpenAI(base_url=a.direct_url, api_key=os.getenv('LLM_BACKEND_KEY', 'x'), timeout=300)
proxy = OpenAI(base_url=a.proxy_url, api_key=os.environ['LITELLM_MASTER_KEY'], timeout=300)
rows = {}
for thinking in (False, True):
    for name, client, model in [('direct', direct, a.direct_model), ('litellm', proxy, a.proxy_model)]:
        t = time.perf_counter()
        response = client.chat.completions.create(
            model=model,
            messages=[{'role': 'user', 'content': 'Return a one-line shell command that prints the word ready.'}],
            max_tokens=2048, temperature=0,
            extra_body={'chat_template_kwargs': {'enable_thinking': thinking}})
        choice = response.choices[0]
        msg = choice.message.model_dump()
        rows[f'{name}-thinking-{"on" if thinking else "off"}'] = {
            'elapsed_s': time.perf_counter() - t,
            'reasoning_content': msg.get('reasoning_content') or msg.get('reasoning'),
            'content': msg.get('content'),
            'finish_reason': choice.finish_reason,
            'usage': response.usage.model_dump() if response.usage else None,
            'raw_message': msg,
        }
comparison = {}
for mode in ('off', 'on'):
    d, l = rows[f'direct-thinking-{mode}'], rows[f'litellm-thinking-{mode}']
    comparison[mode] = {
        'reasoning_content_equal': d['reasoning_content'] == l['reasoning_content'],
        'content_equal': d['content'] == l['content'],
        'finish_reason_equal': d['finish_reason'] == l['finish_reason'],
        'usage_equal': d['usage'] == l['usage'],
        'direct_has_reasoning': bool(d['reasoning_content']),
        'litellm_has_reasoning': bool(l['reasoning_content']),
    }
comparison['enable_thinking_honoured_through_proxy'] = (
    not comparison['off']['litellm_has_reasoning'] and comparison['on']['litellm_has_reasoning'])
path = Path(a.out)
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps({'models': rows, 'comparison': comparison}, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(json.dumps(comparison, ensure_ascii=False))
