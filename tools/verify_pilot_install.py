"""Verify installed package/parsers in a private clean venv; no provider calls."""
import argparse
import importlib.metadata as metadata
import json
from pathlib import Path
import site
import sys
import tempfile


def verify(output):
    import sourceroi
    from sourceroi.live.ingest import _extract
    from docx import Document
    from pypdf import PdfWriter
    output=Path(output)
    if output.exists():raise ValueError('Choose a new output path')
    assert sys.prefix != sys.base_prefix, 'Use an isolated virtual environment'
    assert site.ENABLE_USER_SITE is False, 'User site must be disabled'
    assert Path(sourceroi.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()), 'Imported working checkout instead of installed wheel'
    checks={}
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory)
        doc=Document();doc.add_paragraph('Synthetic parser installation check')
        table=doc.add_table(rows=1, cols=2);table.cell(0,0).text='attribute';table.cell(0,1).text='value'
        path=root/'fixture.docx';doc.save(path)
        text=_extract(path);assert 'Synthetic parser installation check' in text and 'attribute | value' in text
        checks['docx']='PASS: generated paragraph and table'
        pdf=PdfWriter();pdf.add_blank_page(width=72,height=72);path=root/'fixture.pdf'
        with path.open('wb') as stream:pdf.write(stream)
        assert '[Page 1]' in _extract(path)
        checks['pdf']='PASS: blank PDF structure; no OCR/complex-document claim'
        for name,value,expected in [('fixture.txt','Synthetic text','Synthetic text'),('fixture.md','# Synthetic','Synthetic'),
                                    ('fixture.csv','attribute,value\nx,12\n','attribute: x'),
                                    ('fixture.json','{"attribute":12}','attribute'),
                                    ('fixture.jsonl','{"attribute":12}\n','attribute'),
                                    ('fixture.html','<p>Synthetic</p><script>bad()</script>','Synthetic')]:
            path=root/name;path.write_text(value)
            result=_extract(path);assert expected in result
            if path.suffix=='.html':assert 'bad()' not in result
            checks[path.suffix]='PASS'
    result={'status':'VERIFIED','python':sys.version,'prefix':sys.prefix,'base_prefix':sys.base_prefix,
            'installed_package':sourceroi.__file__,'user_site_enabled':site.ENABLE_USER_SITE,
            'parsers':checks,'model_calls':0,'independent_validation':False,
            'versions':{n:metadata.version(n) for n in ('sourceroi','fastapi','uvicorn','httpx','pypdf','python-docx','lxml','pytest')}}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as stream:json.dump(result,stream,indent=2)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    print(json.dumps(verify(p.parse_args().output),indent=2))
