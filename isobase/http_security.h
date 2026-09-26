/* Controller-only access policy. No credential is passed to query workers. */
#include <strings.h>
static unsigned char owner_token[256];
static size_t owner_token_length;
static unsigned short bound_port;
static int token_character(unsigned char c) {
  return (c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='_'||c=='-';
}
static int load_owner_token(const char *path) {
  int fd=open(path,O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC);
  if(fd<0)return 0;
  struct stat st;unsigned char bytes[258];size_t used=0;int good=1;
  if(fstat(fd,&st)||!S_ISREG(st.st_mode)||st.st_uid!=geteuid()||(st.st_mode&077))good=0;
  while(good&&used<sizeof bytes) {
    ssize_t n=read(fd,bytes+used,sizeof bytes-used);
    if(n<0&&errno==EINTR)continue;
    if(n<0){good=0;break;}if(!n)break;used+=(size_t)n;
  }
  close(fd);
  if(used&&bytes[used-1]=='\n')used--;
  if(used<32||used>sizeof owner_token)good=0;
  for(size_t i=0;i<used;i++)if(!token_character(bytes[i]))good=0;
  if(good){memcpy(owner_token,bytes,used);owner_token_length=used;}
  memset(bytes,0,sizeof bytes);return good;
}
static int authorized(const char *value) {
  if(!owner_token_length)return 1;
  if(!value||strncasecmp(value,"Bearer ",7))return 0;
  value+=7;while(*value==' ')value++;
  size_t length=strlen(value);unsigned int difference=(unsigned int)(length^owner_token_length);
  for(size_t i=0;i<sizeof owner_token;i++)difference|=owner_token[i]^(i<length?(unsigned char)value[i]:0);
  return difference==0;
}
static int field_character(unsigned char c) {
  return token_character(c)||strchr("!#$%&'*+.^`|~",c)!=NULL;
}
/* Mutates complete header lines. Return status and a non-sensitive reason. */
static int check_headers(char *p,const char **reason) {
  char *host=NULL,*auth=NULL,*origin=NULL,*site=NULL,*length=NULL;
  *reason="invalid_headers";
  while(strcmp(p,"\r\n")) {
    char *end=strstr(p,"\r\n");if(!end)return 400;*end=0;
    char *colon=strchr(p,':');if(!colon||colon==p)return 400;
    for(char *q=p;q<colon;q++)if(!field_character((unsigned char)*q))return 400;
    *colon=0;char *value=colon+1;
    for(char *q=value;*q;q++)if(((unsigned char)*q<32&&*q!='\t')||(unsigned char)*q==127)return 400;
    while(*value==' '||*value=='\t')value++;
    char *tail=end;while(tail>value&&(tail[-1]==' '||tail[-1]=='\t'))*--tail=0;
    char **slot=NULL;
    if(!strcasecmp(p,"Host"))slot=&host;
    else if(!strcasecmp(p,"Authorization"))slot=&auth;
    else if(!strcasecmp(p,"Origin"))slot=&origin;
    else if(!strcasecmp(p,"Sec-Fetch-Site"))slot=&site;
    else if(!strcasecmp(p,"Content-Length"))slot=&length;
    else if(!strcasecmp(p,"Transfer-Encoding"))return 400;
    if(slot){if(*slot)return 400;*slot=value;}
    p=end+2;
  }
  if(!host||(length&&strcmp(length,"0")))return 400;
  char ip[64],name[64];snprintf(ip,sizeof ip,"127.0.0.1:%u",bound_port);snprintf(name,sizeof name,"localhost:%u",bound_port);
  if(strcasecmp(host,ip)&&strcasecmp(host,name)&&!(bound_port==80&&(!strcasecmp(host,"localhost")||!strcmp(host,"127.0.0.1")))) {
    *reason="invalid_host";return 403;
  }
  if(origin) {
    char expected[96];snprintf(expected,sizeof expected,"http://%s",host);
    if(strcasecmp(origin,expected)){*reason="invalid_origin";return 403;}
  }
  if(site&&strcmp(site,"same-origin")&&strcmp(site,"none")){*reason="cross_site_request";return 403;}
  if(!authorized(auth)){*reason="authentication_required";return 401;}
  return 0;
}
