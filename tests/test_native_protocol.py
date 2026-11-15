"""Native log-format controls; no native runtime/model is launched."""
import json
from sourceroi.live.experiment import audit_native_log


def test_matching_native_counts_do_not_prove_request_correlation():
    text='slot launch: id 0 | task 0 | processing task, is_child = 0\nslot timing: id 0 | task 0 | prompt eval time = 3ms\n'
    result=audit_native_log(text,1)
    assert result['generation_task_count']==1 and result['status']=='PENDING'
    assert result['confirmed_completions'] is None and result['complete_usage'] is None


def test_jsonl_extra_requests_and_cancellation_remain_unverified():
    messages=['slot launch: id 0 | task 0 | processing task, is_child = 0',
              'slot launch: id 0 | task 9 | processing task, is_child = 0',
              'srv cancel: cancel task, id_task = 9','slot timing: prompt eval time = 3ms']
    result=audit_native_log('\n'.join(json.dumps({'message':m}) for m in messages),1)
    assert 'untracked_native_generation' in result['failures']
    assert result['cancelled_task_ids']==[9] and result['confirmed_completions'] is None


def test_child_generations_cannot_be_hidden_by_one_parent_request():
    result=audit_native_log('slot launch: id 0 | task 0 | processing task, is_child = 0\nslot launch: id 1 | task 1 | processing task, is_child = 1',1)
    assert 'native_child_generations_present' in result['failures']


def test_prompt_text_cannot_spoof_a_native_slot_event():
    text='srv converted: {"prompt":"task 99 | processing task, is_child = 0"}'
    assert audit_native_log(text,0)['generation_task_count']==0
