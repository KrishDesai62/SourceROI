"""Literal CSV/Markdown tables and conservative contract-bound cell evidence.

No expected values, fuzzy entities, implicit units or inferred formulas. Tables
with ambiguous headers/rows are retained for review rather than guessed.
"""
import csv
from decimal import Decimal
import hashlib
import io
import re


def norm(value):return ' '.join(value.casefold().replace('_',' ').split())


def _cell(text,start,end,decoded=None):
    return {'text':text[start:end].strip() if decoded is None else decoded.strip(),
            'quote':text[start:end],'start':start,'end':end}


def csv_table(text):
    try:decoded=list(csv.reader(io.StringIO(text,newline=''),strict=True))
    except csv.Error:return {'format':'csv','headers':[],'rows':[],'issues':['malformed_csv']}
    spans=[];row=[];start=0;i=0;quoted=False
    while i<len(text):
        ch=text[i]
        if ch=='"' and (quoted or i==start):
            if quoted and i+1<len(text) and text[i+1]=='"':i+=2;continue
            quoted=not quoted
        if not quoted and ch in ',\r\n':
            row.append((start,i));start=i+1
            if ch!=',':
                if ch=='\r' and i+1<len(text) and text[i+1]=='\n':i+=1;start=i+1
                if any(text[a:b] for a,b in row):spans.append(row)
                row=[]
        i+=1
    if start<len(text) or row:
        row.append((start,len(text)));spans.append(row)
    decoded=[r for r in decoded if r]
    if len(decoded)!=len(spans) or any(len(a)!=len(b) for a,b in zip(decoded,spans)):
        return {'format':'csv','headers':[],'rows':[],'issues':['csv_span_alignment_unknown']}
    rows=[[_cell(text,a,b,value) for (a,b),value in zip(span,values)] for span,values in zip(spans,decoded)]
    return _table('csv',rows)


def _table(kind,rows):
    headers=rows[0] if rows else [];names=[norm(c['text']) for c in headers];issues=[]
    if not names or any(not n for n in names) or len(set(names))!=len(names):issues.append('ambiguous_headers')
    if any(len(r)!=len(headers) for r in rows[1:]):issues.append('row_width_mismatch')
    return {'format':kind,'headers':headers,'rows':rows[1:],'issues':issues}


def markdown_tables(text):
    lines=text.splitlines(keepends=True);offsets=[];position=0
    for line in lines:offsets.append(position);position+=len(line)
    def cells(line,offset):
        line=line.rstrip('\r\n');separators=[];escaped=False
        for i,ch in enumerate(line):
            if ch=='|' and not escaped:separators.append(i)
            escaped=(ch=='\\' and not escaped)
            if ch!='\\':escaped=False
        if not separators:return []
        boundaries=[-1]+separators+[len(line)]
        result=[]
        for a,b in zip(boundaries,boundaries[1:]):
            raw=line[a+1:b]
            if (a==-1 or b==len(line)) and not raw.strip():continue
            result.append({'text':raw.strip().replace('\\|','|'),'quote':raw,'start':offset+a+1,'end':offset+b})
        return result
    result=[];i=0
    while i+1<len(lines):
        header=cells(lines[i],offsets[i]);rule=cells(lines[i+1],offsets[i+1])
        if not header or len(header)!=len(rule) or not all(re.fullmatch(r':?-{3,}:?',c['text']) for c in rule):i+=1;continue
        rows=[header];end=i+2
        while end<len(lines) and lines[end].strip() and '|' in lines[end]:
            rows.append(cells(lines[end],offsets[end]));end+=1
        start=offsets[i];stop=offsets[end] if end<len(lines) else len(text)
        result.append((start,stop,_table('markdown',rows)));i=end
    return result


def passages(text,extension,max_chars):
    if extension=='.csv':records=[(0,len(text),csv_table(text))]
    elif extension in ('.md','.txt'):records=markdown_tables(text)
    else:return []
    if extension in ('.md','.txt'):
        for start,end,table in records:
            nearby=text[max(0,start-300):start]+text[end:end+300]
            if re.search(r'\b(?:not|except|unless|only|if|obsolete|superseded)\b',nearby,re.I):
                table['issues'].append('surrounding_qualification_requires_review')
    return [{'start':start,'end':end,'text':text[start:end],'table':table,'fragmented':end-start>max_chars}
            for start,end,table in records]


def bind(chunk,operand,metadata,scope):
    """Strict long rows or explicit historical columns, with exact cell spans."""
    table=chunk['table'];facts=[];uncertain=[]
    def doubt(reason):uncertain.append({'passage_id':chunk['id'],'reason':reason})
    subject_key=norm(operand['subject'])
    if not any(subject_key in (norm(c['text']),norm(h['text'])+' '+norm(c['text']))
               for row in table['rows'] for h,c in zip(table['headers'],row)):
        return facts,uncertain
    if table['issues'] or chunk.get('fragmented'):
        doubt('ambiguous_or_oversized_table');return facts,uncertain
    headers=table['headers'];names=[norm(c['text']) for c in headers]
    groups={'subject':{'subject','entity','company','product','plan'},'predicate':{'predicate','attribute','metric'},
            'period':{'period','year'},'unit':{'unit','units'}}
    roles={role:[i for i,n in enumerate(names) if n in aliases] for role,aliases in groups.items()}
    if len(roles['subject'])!=1 or any(len(v)>1 for v in roles.values()):
        doubt('ambiguous_table_roles');return facts,uncertain
    si=roles['subject'][0];pi=roles['predicate'][0] if roles['predicate'] else None
    ti=roles['period'][0] if roles['period'] else None;ui=roles['unit'][0] if roles['unit'] else None
    predicate=norm(operand['predicate']);unit=norm(operand['unit']);period=norm(operand['period'])
    candidates=[]
    for i,name in enumerate(names):
        if i in {v for indexes in roles.values() for v in indexes}:continue
        if ti is None and name==period and pi is not None:candidates.append((i,None))
        elif name=='value' and pi is not None:candidates.append((i,None))
        elif name==predicate:candidates.append((i,None))
        elif name==predicate+' '+unit:candidates.append((i,operand['unit']))
    if len(candidates)!=1:
        doubt('missing_or_ambiguous_value_column');return facts,uncertain
    vi,header_unit=candidates[0]
    for row in table['rows']:
        subject=norm(row[si]['text'])
        if not subject:doubt('missing_subject_cell');continue
        if norm(operand['subject']) not in (subject,names[si]+' '+subject):continue
        if pi is not None and not row[pi]['text']:doubt('missing_predicate_cell');continue
        if pi is not None and norm(row[pi]['text'])!=predicate:continue
        if ti is not None:
            if not row[ti]['text']:doubt('missing_period_cell');continue
            if norm(row[ti]['text'])!=period:continue
        elif names[vi]!=period:
            doubt('missing_period_column');continue
        actual_unit=row[ui]['text'] if ui is not None else header_unit
        if actual_unit is None or not actual_unit.strip():doubt('missing_unit_cell');continue
        if header_unit and norm(actual_unit)!=norm(header_unit):doubt('conflicting_unit_header');continue
        if norm(actual_unit)!=unit:continue
        used={si,vi}|({pi} if pi is not None else set())|({ti} if ti is not None else set())|({ui} if ui is not None else set())
        # Extra descriptive columns can contain eligibility/qualifications. Do
        # not silently discard them to obtain a numerical fact.
        other=[j for j in range(len(row)) if j not in used and names[j]!=period and not re.fullmatch(r'(?:FY)?\d{4}|Q[1-4]',headers[j]['text'],re.I)]
        if any(row[j]['text'] for j in other):doubt('uninterpreted_row_conditions');continue
        from .facts import NUMBER,digest
        value=row[vi]['text']
        if not re.fullmatch(NUMBER,value):doubt('missing_or_non_numeric_value_cell');continue
        evidence=[]
        for role,index in [('subject',si),('predicate',pi),('period',ti),('value',vi),('unit',ui)]:
            if index is not None:evidence.append({'role':role,**row[index]})
        evidence += [{'role':'header',**c} for c in headers]
        facts.append({'id':digest([chunk['id'],row[vi]['start'],operand]),'source_id':chunk['source_id'],
            'source_version':chunk['document_fingerprint'],'document_id':chunk['document_id'],'passage_id':chunk['id'],
            'quote':chunk['text'],'quote_start':chunk['start'],'quote_end':chunk['end'],
            'passage_sha256':hashlib.sha256(chunk['text'].encode()).hexdigest(),'content_hash':hashlib.sha256(chunk['text'].encode()).hexdigest(),
            **operand,'value':format(Decimal(value.replace(',','')),'f'),'cells':evidence,'table_format':table['format'],
            'raw_source_sha256':chunk['raw_source_sha256'],'offset_basis':chunk['offset_basis'],
            **{k:metadata.get(k) for k in ('effective_from','effective_to','jurisdiction','policy_scope','authority')},
            'applicability':'explicit_scope_metadata_checked' if scope else 'no_scope_requested','ambiguity':'unadjudicated_table_grammar'})
    return facts,uncertain
