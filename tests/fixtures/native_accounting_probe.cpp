#include "accounting.h"
#include <string>
int main(int argc,char **argv) {
    std::string mode=argc>1?argv[1]:"normal",id="abc-1";
    if(mode=="untracked"){sr_audit::dispatch(999,false);return 1;}
    if(!sr_audit::admit(id,"{}"))return 3;
    sr_audit::bind(id,7);
    if(mode=="duplicate")return sr_audit::admit(id,"{}")?4:0;
    sr_audit::dispatch(7,mode=="child");
    if(mode=="cancel"){sr_audit::terminal(7,"cancelled");return 0;}
    if(mode=="failed"){sr_audit::terminal(7,"failed");return 0;}
    sr_audit::finish(7,3,4);
    if(mode=="double_finish")sr_audit::finish(7,3,4);
    sr_audit::http(id,200,"{\"usage\":{\"prompt_tokens\":3,\"completion_tokens\":4,\"total_tokens\":7}}");
    return 0;
}
