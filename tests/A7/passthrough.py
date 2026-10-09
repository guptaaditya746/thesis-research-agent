from __future__ import annotations
import json
import os
import time
from pathlib import Path
from openai import OpenAI

request = {
    'model': 'heavy-model',
    'messages': [{'role': 'user', 'content': 'Return a one-line shell command that prints the word ready.'}],
    'max_tokens': 96,
    'temperature': 0,
    'extra_body': {'chat_template_kwargs': {'enable_thinking': False}},
}
direct = OpenAI(base_url='http://127.0.0.1:8002/v1', api_key='x', timeout=120)
proxy = OpenAI(base_url='http://127.0.0.1:4000/v1', api_key=os.environ['LITELLM_MASTER_KEY'], timeout=120)
rows = {}
for name, client in [('direct', direct), ('litellm', proxy)]:
    t = time.perf_counter()
    response = client.chat.completions.create(**request)
    choice = response.choices[0]
    msg = choice.message.model_dump()
    rows[name] = {
        'elapsed_s': time.perf_counter() - t,
        'reasoning_content': msg.get('reasoning_content'),
        'content': msg.get('content'),
        'finish_reason': choice.finish_reason,
        'usage': response.usage.model_dump() if response.usage else None,
        'raw_message': msg,
    }
comparison = {
    'reasoning_content_equal': rows['direct']['reasoning_content'] == rows['litellm']['reasoning_content'],
    'content_equal': rows['direct']['content'] == rows['litellm']['content'],
    'finish_reason_equal': rows['direct']['finish_reason'] == rows['litellm']['finish_reason'],
    'usage_equal': rows['direct']['usage'] == rows['litellm']['usage'],
    'enable_thinking_false': 'chat_template_kwargs.enable_thinking=False',
}
output = {'models': rows, 'comparison': comparison}
path = Path('tests/A7/result.json')
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(output, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(json.dumps({'comparison': comparison, 'direct_elapsed_s': rows['direct']['elapsed_s'], 'proxy_elapsed_s': rows['litellm']['elapsed_s']}, ensure_ascii=False))
