#pragma once
// SourceROI local-only instrumented runtime. No networking or model code here.
#include <algorithm>
#include <chrono>
#include <cstdlib>
#include <fcntl.h>
#include <fstream>
#include <map>
#include <mutex>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unistd.h>
namespace sr_audit {
inline std::mutex lock;
inline std::map<int,std::string> task_ids;
inline std::map<std::string,std::string> state;
inline int admissions=0;
inline auto started=std::chrono::steady_clock::now();
inline std::string env(const char *key) {const char *v=std::getenv(key); return v?v:"";}
inline std::string quoted(const std::string &s) {
    std::ostringstream o;o<<'"';
    for(unsigned char c:s) {if(c=='"'||c=='\\')o<<'\\'<<c;else if(c<32){const char *h="0123456789abcdef";o<<"\\u00"<<h[c>>4]<<h[c&15];}else o<<c;}
    o<<'"';return o.str();
}
inline void emit(const std::string &event,const std::string &id,int task=-1,int input=-1,int output=-1,int code=0,const std::string &body="") {
    std::ostringstream o;o<<"{\"event\":"<<quoted(event)<<",\"request_id\":"<<quoted(id)<<",\"task_id\":"<<task<<",\"input_tokens\":"<<input<<",\"output_tokens\":"<<output<<",\"code\":"<<code<<",\"body\":"<<quoted(body)<<"}\n";
    std::string line=o.str(),path=env("SOURCEROI_NATIVE_AUDIT");
    int fd=open(path.c_str(),O_WRONLY|O_APPEND|O_CREAT|O_CLOEXEC|O_NOFOLLOW,0600);
    if(fd<0)std::abort();
    size_t n=0;while(n<line.size()){ssize_t w=write(fd,line.data()+n,line.size()-n);if(w<=0)std::abort();n+=w;}
    if(fsync(fd)!=0)std::abort();close(fd);
}
inline bool admit(const std::string &id,const std::string &body) {
    std::lock_guard<std::mutex> guard(lock);
    if(id.empty()||id.find_first_not_of("0123456789abcdef-")!=std::string::npos||id.size()>80){emit("denied",id);return false;}
    int limit=std::atoi(env("SOURCEROI_NATIVE_MAX_CALLS").c_str());
    double seconds=std::atof(env("SOURCEROI_NATIVE_MAX_SECONDS").c_str());
    double elapsed=std::chrono::duration<double>(std::chrono::steady_clock::now()-started).count();
    if(state.count(id)||limit<=0||admissions>=limit||seconds<=0||elapsed>=seconds){emit("denied",id);return false;}
    std::string path=env("SOURCEROI_NATIVE_PERMITS")+"/"+id;
    std::ifstream file(path,std::ios::binary);std::string allowed((std::istreambuf_iterator<char>(file)),{});
    if(!file.is_open()||allowed!=body||unlink(path.c_str())!=0){emit("denied",id);return false;}
    ++admissions;state[id]="admitted";emit("admitted",id,-1,-1,-1,0,body);return true;
}
inline void bind(const std::string &id,int task) {
    std::lock_guard<std::mutex> guard(lock);
    if(state[id]!="admitted"||task_ids.count(task))throw std::runtime_error("SourceROI untracked or child generation refused");
    state[id]="bound";task_ids[task]=id;emit("bound",id,task);
}
inline void dispatch(int task,bool child) {
    std::lock_guard<std::mutex> guard(lock);
    if(child||!task_ids.count(task)||state[task_ids[task]]!="bound") {emit("untracked_task","",task);std::abort();}
    auto id=task_ids[task];state[id]="dispatched";emit("dispatched",id,task);
}
inline void finish(int task,int input,int output) {
    std::lock_guard<std::mutex> guard(lock);
    if(!task_ids.count(task)||state[task_ids[task]]!="dispatched") {emit("untracked_finish","",task);std::abort();}
    auto id=task_ids[task];state[id]="completed";emit("completed",id,task,input,output);
}
inline void terminal(int task,const std::string &event) {
    std::lock_guard<std::mutex> guard(lock);
    if(!task_ids.count(task))return;
    auto id=task_ids[task];if(state[id]=="completed"||state[id]=="failed"||state[id]=="cancelled")return;
    state[id]=event;emit(event,id,task); // usage intentionally unknown
}
inline void http(const std::string &id,int code,const std::string &body) {
    std::lock_guard<std::mutex> guard(lock);emit("http_response",id,-1,-1,-1,code,body);
}
inline std::string request_id(const std::map<std::string,std::string> &headers) {
    for(auto &p:headers){auto k=p.first;std::transform(k.begin(),k.end(),k.begin(),[](unsigned char c){return std::tolower(c);});if(k=="x-sourceroi-request")return p.second;}
    return "";
}
}
