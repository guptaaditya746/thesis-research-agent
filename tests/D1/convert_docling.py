from __future__ import annotations
import json
import time
from pathlib import Path
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

repo = Path(__file__).resolve().parents[2]
ids = json.loads((repo / 'tests/D1/selection.json').read_text())
source = repo / 'final-final-frontend/corpus_acl_emnlp_2025_input'
out = repo / 'tests/D1/docling'
out.mkdir(parents=True, exist_ok=True)
options = PdfPipelineOptions(do_ocr=False, do_table_structure=True)
converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)})
rows = []
for pid in ids:
    venue, paper_no = pid[5:].rsplit('-', 1)
    pdf = source / f'2025.{venue}.{paper_no}.pdf'
    start = time.perf_counter()
    try:
        result = converter.convert(pdf)
        markdown = result.document.export_to_markdown()
        (out / f'{pid}.md').write_text(markdown, encoding='utf-8')
        row = {'paper_id': pid, 'pdf': str(pdf), 'seconds': time.perf_counter() - start, 'chars': len(markdown), 'error': None}
    except Exception as exc:
        row = {'paper_id': pid, 'pdf': str(pdf), 'seconds': time.perf_counter() - start, 'chars': 0, 'error': f'{type(exc).__name__}: {exc}'}
    rows.append(row)
    print(json.dumps(row, ensure_ascii=False), flush=True)
(repo / 'tests/D1/docling_times.json').write_text(json.dumps(rows, indent=2, ensure_ascii=False) + '\n')
