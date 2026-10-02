#ifndef ISO_CREDENTIAL_FILE_H
#define ISO_CREDENTIAL_FILE_H
#include <errno.h>
#include <sys/stat.h>
#include <unistd.h>
#ifdef __APPLE__
#include <sys/acl.h>
#elif defined(__linux__)
#include <sys/xattr.h>
#endif
static inline void credential_wipe(void *buffer,size_t length) {
  volatile unsigned char *p=buffer;while(length--)*p++=0;
}
/* Conservative: reject extended ACLs rather than infer their effective grants. */
static inline int credential_private_fd(int fd) {
  struct stat st;
  if(fstat(fd,&st) || !S_ISREG(st.st_mode) || st.st_uid!=geteuid() || (st.st_mode&077))return 0;
#ifdef __APPLE__
  acl_t acl=acl_get_fd_np(fd,ACL_TYPE_EXTENDED);
  if(!acl)return errno==ENOENT; /* Darwin: descriptor has no extended ACL. */
  if(acl_valid(acl)){acl_free(acl);return 0;}
  acl_entry_t entry;errno=0;int result=acl_get_entry(acl,ACL_FIRST_ENTRY,&entry);
  int empty=result==-1 && errno==EINVAL;
  acl_free(acl);return empty;
#elif defined(__linux__)
  ssize_t size=fgetxattr(fd,"system.posix_acl_access",NULL,0);
  return size<0 && (errno==ENODATA || errno==ENOTSUP);
#else
  return 0;
#endif
}
#endif
