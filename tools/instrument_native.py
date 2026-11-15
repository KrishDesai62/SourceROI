"""Apply exact accounting hooks to the approved b12345 source, not system binaries."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parents[1]


def instrument(source,output):
    source=Path(source);target=source/'tools/server'
    changes={}
    def edit(name,replacements):
        path=target/name;before=path.read_text();text=before
        for old,new in replacements:
            if text.count(old)!=1:raise ValueError('Source hook missing/ambiguous: '+name+' '+old[:60])
            text=text.replace(old,new,1)
        path.write_text(text);changes[name]={'before_sha256':hashlib.sha256(before.encode()).hexdigest(),'after_sha256':hashlib.sha256(text.encode()).hexdigest()}
    shutil.copy2(ROOT/'sourceroi/live/native/accounting.h',target/'sourceroi-accounting.h')
    edit('server-http.cpp',[
        ('#include "common.h"','#include "common.h"\n#include "sourceroi-accounting.h"'),
        ('    // srv->set_logger(log_server_request); // TODO @ngxson : this is too spamy, no very useful; improve it in the future',
         '    srv->set_logger([](const httplib::Request &req,const httplib::Response &res){if(req.method=="POST")sr_audit::http(req.get_header_value("X-SourceROI-Request"),res.status,res.body);});'),
        ('        std::string body = req.body;', '''        if(req.path!="/v1/chat/completions" && req.path!="/tokenize") {res.status=403;return;}
        if(req.path=="/v1/chat/completions") {
            auto body_check=json::parse_no_throw(req.body);
            if(body_check.is_discarded() || !body_check.is_object() || json_value(body_check,"stream",false) || json_value(body_check,"n",1)!=1 || json_value(body_check,"best_of",1)!=1 || !sr_audit::admit(req.get_header_value("X-SourceROI-Request"),req.body)) {res.status=403;return;}
        }
        std::string body = req.body;''')])
    edit('server-context.cpp',[
        ('#include "server-context.h"','#include "server-context.h"\n#include "sourceroi-accounting.h"'),
        ('        slot.task = std::make_unique<const server_task>(std::move(task));','        sr_audit::dispatch(task.id,task.is_child());\n        slot.task = std::make_unique<const server_task>(std::move(task));'),
        ('    void send_final_response(server_slot & slot) {','    void send_final_response(server_slot & slot) {\n        sr_audit::finish(slot.task->id,slot.task->n_tokens(),slot.stats.n_gen);'),
        ('        SRV_ERR("task id = %d, error: %s\\n", id_task, error.c_str());','        sr_audit::terminal(id_task,"failed");\n        SRV_ERR("task id = %d, error: %s\\n", id_task, error.c_str());'),
        ('            case SERVER_TASK_TYPE_CANCEL:\n                {','            case SERVER_TASK_TYPE_CANCEL:\n                {\n                    sr_audit::terminal(task.id_target,"cancelled");'),
        ('        // tasks.reserve(inputs.size()); // TODO: this is inaccurate due to child tasks','        if(inputs.size()!=1 || json_value(data,"n",1)!=1 || json_value(data,"stream",false))throw std::runtime_error("SourceROI requires one non-streamed generation");\n        // tasks.reserve(inputs.size()); // TODO: this is inaccurate due to child tasks'),
        ('            // prepare child tasks','            if(task.params.n_cmpl!=1)throw std::runtime_error("SourceROI child generation refused");\n            sr_audit::bind(sr_audit::request_id(req.headers),task.id);\n            // prepare child tasks')])
    output=Path(output)
    with output.open('x') as f:json.dump({'source':str(source),'changes':changes,'header_sha256':hashlib.sha256((target/'sourceroi-accounting.h').read_bytes()).hexdigest()},f,indent=2)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();instrument(a.source,a.output)
