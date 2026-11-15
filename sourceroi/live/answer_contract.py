"""Explicit response types. No unit stripping, answer guessing or label rewriting."""
import json
import math
import re

NUMBER=r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?'


def validate(contract):
    if contract is None:return
    if not isinstance(contract,dict) or set(contract)-{'version','type','schema'} or contract.get('version')!=1 or contract.get('type') not in ('numeric','text','boolean','structured'):
        raise ValueError('Answer contract must be version 1 with a supported type')
    if contract['type']=='structured':
        schema=contract.get('schema',{})
        if not isinstance(schema,dict) or set(schema)-{'type','properties','required','additionalProperties'} or schema.get('type')!='object' or schema.get('additionalProperties') is not False:
            raise ValueError('Structured contract supports a closed flat JSON object')
        fields=schema.get('properties',{});required=schema.get('required',[])
        if not isinstance(fields,dict) or not fields or len(fields)>32 or not isinstance(required,list) or any(not isinstance(k,str) or k not in fields for k in required):raise ValueError('Invalid structured fields')
        if any(not isinstance(v,dict) or set(v)!={'type'} or v['type'] not in ('string','number','boolean') for v in fields.values()):raise ValueError('Structured fields must be scalar types')
    elif 'schema' in contract:raise ValueError('Schema applies only to structured answers')


def check(value,contract):
    validate(contract)
    if contract is None:return True,'legacy scalar normalization'
    if value=='INSUFFICIENT_EVIDENCE':return True,'explicit abstention, not a factual answer'
    kind=contract['type']
    if kind=='numeric':valid=(type(value) is int or type(value) is float and math.isfinite(value)) or isinstance(value,str) and re.fullmatch(NUMBER,value) is not None
    elif kind=='text':valid=isinstance(value,str) and bool(value.strip())
    elif kind=='boolean':valid=type(value) is bool or isinstance(value,str) and value in ('true','false')
    else:
        s=contract['schema'];valid=isinstance(value,dict)
        if valid:
            valid=set(value)<=set(s['properties']) and set(s.get('required',[]))<=set(value)
            for k,v in value.items():
                t=s['properties'].get(k,{}).get('type')
                valid=valid and ((isinstance(v,str) and t=='string') or (type(v) is bool and t=='boolean') or ((type(v) is int or type(v) is float and math.isfinite(v)) and t=='number'))
    return bool(valid),'declared '+kind+' shape satisfied' if valid else 'answer violates declared '+kind+' shape; no semantic coercion applied'


def schema(contract):
    validate(contract)
    if contract is None:return {'type':['string','number','boolean']}
    return {'numeric':{'type':'number'},'text':{'type':'string'},'boolean':{'type':'boolean'},'structured':contract.get('schema')}[contract['type']]


def normalize(value,contract):
    if isinstance(value,dict) and contract and contract['type']=='structured':return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
    if isinstance(value,str):return value
    if type(value) is bool:return 'true' if value else 'false'
    if type(value) is int:return str(value)
    if type(value) is float and math.isfinite(value):return json.dumps(value,allow_nan=False)
    raise ValueError('Unsupported answer value')
