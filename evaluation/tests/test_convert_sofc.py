import zipfile

from evaluation.realpapers.convert_sofc import convert


def test_converts_sentence_offsets_repeated_slots_and_uncertain_values(tmp_path):
    archive = tmp_path / 'release.zip'
    prefix = 'release/sofc-exp-corpus/'
    text = 'header\nA 12 mW and 8 mW cell'
    with zipfile.ZipFile(archive, 'w') as z:
        z.writestr(prefix + 'texts/PMC1.txt', text)
        z.writestr(prefix + 'annotations/sentences/PMC1.csv', '1\t0\t0\t6\n2\t1\t7\t28\n')
        z.writestr(prefix + 'annotations/frames/PMC1.csv',
                   'SPAN\t1\tVALUE\t2\t2\t7\nSPAN\t2\tVALUE\t2\t12\t16\n'
                   'SPAN\t3\tEXPERIMENT:current_exp\t2\t17\t21\n'
                   'EXPERIMENT\t1\t3\n\tpower_density\t1\n\tpower_density\t2\n'
                   'LINK\tcoreference\t1\t2\n')
    paper = convert(archive)['papers'][0]
    assert paper['values'][0]['raw'] == '12 mW'
    assert paper['values'][0]['value'] == 12
    assert paper['values'][0]['material'] is None
    assert paper['experiments'][0]['slots']['power_density'] == '12 mW; 8 mW'
    assert paper['links'] == [{'type': 'coreference', 'source': '1', 'target': '2'}]
