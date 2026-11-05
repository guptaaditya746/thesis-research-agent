"""Test source relationships and exclusions in the MeasEval converter."""
import json
from zipfile import ZipFile

import pytest

from evaluation.realpapers.convert_measeval import convert


def test_converts_source_spans_and_property_relation_without_inventing_range(tmp_path):
    archive = tmp_path / 'source.zip'
    text = 'A mass of 39% and 2 to 5 kg.'
    rows = [
        ('1', 'Quantity', 10, 13, 'T1', '39%', {'unit': '%'}),
        ('1', 'MeasuredProperty', 2, 6, 'T2', 'mass', {'HasQuantity': 'T1'}),
        ('1', 'MeasuredEntity', 0, 1, 'T3', 'A', {'HasProperty': 'T2'}),
        ('2', 'Quantity', 18, 27, 'T4', '2 to 5 kg', {'unit': 'kg', 'mods': ['IsRange']}),
    ]
    tsv = 'docId\tannotSet\tannotType\tstartOffset\tendOffset\tannotId\ttext\tother\n'
    for group, kind, start, end, ident, span, other in rows:
        tsv += f'doc\t{group}\t{kind}\t{start}\t{end}\t{ident}\t{span}\t{json.dumps(other)}\n'
    with ZipFile(archive, 'w') as z:
        z.writestr('release/data/eval/text/doc.txt', text)
        z.writestr('release/data/eval/tsv/doc.tsv', tsv)
    paper = convert(archive, 'eval')['papers'][0]
    assert [(q['value'], q['unit'], q['entity']) for q in paper['quantities']] == [(39.0, '%', 'A')]
    assert paper['excluded_quantities'][0]['annotation_id'] == 'T4'
    assert len(paper['annotations']) == 4
    with pytest.raises(ValueError, match='no TSV'):
        convert(archive, 'train')


def test_a_converted_release_is_scored_as_its_scalar_subset(tmp_path):
    """The score names the subset and counts what the converter left out, so it never reads as full MeasEval."""
    from evaluation.realpapers.measeval import values_check
    data = {"papers": [{"id": "d", "text": "x", "quantities": [{"value": 39.0, "unit": "%", "entity": "A"}],
                        "excluded_quantities": [{"annotation_id": "T4"}]}],
            "conversion": "unambiguous scalar quantities only; excluded annotations retained"}
    (tmp_path / "measeval.json").write_text(json.dumps(data), encoding="utf-8")
    s = values_check([{"document": "d", "value": 39.0, "unit": "%", "entity": "A"}], tmp_path)
    assert s["subset"].startswith("unambiguous scalar quantities only") and s["excluded_quantities"] == 1
