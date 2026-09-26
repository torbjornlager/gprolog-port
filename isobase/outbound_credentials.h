/* Secrets never enter Prolog terms, URL parameters or diagnostic strings. */
#include <errno.h>
static void outbound_wipe(void *buffer,size_t length) {
  volatile unsigned char *p=buffer;while(length--)*p++=0;
}
static int outbound_authorization(const char *path,char header[280]) {
  int fd=open(path,O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC);
  if(fd<0)return 0;
  struct stat st;unsigned char bytes[258]={0};size_t used=0;int good=1;
  if(fstat(fd,&st) || !S_ISREG(st.st_mode) || st.st_uid!=geteuid() || (st.st_mode&077))good=0;
  while(good && used<sizeof bytes) {
    ssize_t n=read(fd,bytes+used,sizeof bytes-used);
    if(n<0 && errno==EINTR)continue;
    if(n<0){good=0;break;}if(!n)break;used+=(size_t)n;
  }
  close(fd);
  if(used && bytes[used-1]=='\n')used--;
  if(used<32 || used>256)good=0;
  for(size_t i=0;i<used;i++) {
    unsigned char c=bytes[i];
    if(!((c>='a'&&c<='z') || (c>='A'&&c<='Z') || (c>='0'&&c<='9') || c=='_' || c=='-'))good=0;
  }
  if(good)snprintf(header,280,"Authorization: Bearer %.*s",(int)used,bytes);
  outbound_wipe(bytes,sizeof bytes);return good;
}
