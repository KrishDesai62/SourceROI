"""Independent ground-truth graders; no LLM self-judging in accuracy metrics."""
from __future__ import annotations
import math
import re


def normalized(text: str) -> str:
    return re.sub(r'\s+', ' ', str(text).lower().replace(',', '').strip())


def grade(actual: str, task: dict) -> bool:
    actual = str(actual)
    expected = str(task['expected'])
    method = task.get('scoring', 'exact')
    if method == 'qa_exact':
        def qa_normalized(value):
            import string
            text = ''.join(ch for ch in str(value).lower() if ch not in string.punctuation)
            return ' '.join(re.sub(r'\b(a|an|the)\b', ' ', text).split())
        answers = task.get('accepted_answers') or [expected]
        return any(qa_normalized(actual) == qa_normalized(value) for value in answers)
    if method=='structured_exact':
        import json
        from .answer_contract import check
        try:
            left=json.loads(actual);right=json.loads(expected)
            valid,_=check(left,task.get('answer_contract'))
            if not valid or not isinstance(left,dict) or set(left)!=set(right):return False
            return all(type(left[k]) is type(right[k]) and left[k]==right[k] or type(left[k]) in (int,float) and type(right[k]) in (int,float) and left[k]==right[k] for k in left)
        except (ValueError,TypeError,KeyError):return False
    if method == 'exact':
        return normalized(actual) == normalized(expected)
    if method == 'contains':
        return normalized(expected) in normalized(actual)
    if method == 'regex':
        from .parser_boundary import run
        return run({'operation':'regex_grade','expected':expected,'actual':actual},{})
    if method == 'numeric':
        pattern = r'[-+]?\$?\d[\d,]*(?:\.\d+)?(?:[eE][-+]?\d+)?'
        m = re.search(pattern, actual)
        t = re.search(pattern, expected)
        if not m or not t:
            return False
        a = float(m.group().replace('$', '').replace(',', ''))
        b = float(t.group().replace('$', '').replace(',', ''))
        return math.isfinite(a) and abs(a - b) <= float(task.get('tolerance', 0))
    raise ValueError(f'Unknown scoring method {method}')


def wilson_interval(success: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    if n <= 0:
        return None
    p = success / n
    d = 1 + z*z/n
    center = (p + z*z/(2*n))/d
    radius = z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/d
    return round(max(0, center-radius), 4), round(min(1, center+radius), 4)
