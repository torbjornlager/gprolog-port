#ifndef ISO_LINUX_QUERY_JAIL_H
#define ISO_LINUX_QUERY_JAIL_H
/* Linux service containment is entered before parsing submitted Prolog.
 * It supplements the language policy; it must not silently fall back. */
#ifdef __linux__
#include <grp.h>
#include <stddef.h>
#include <linux/audit.h>
#include <linux/capability.h>
#include <linux/filter.h>
#include <linux/seccomp.h>
#include <sched.h>
#include <sys/prctl.h>
#include <sys/socket.h>
#include <sys/syscall.h>

static int iso_query_limit(int resource,rlim_t value) {
  struct rlimit limit={value,value};return setrlimit(resource,&limit)==0;
}
#define ISO_DENY_SYSCALL(n) BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,(n),0,1), BPF_STMT(BPF_RET|BPF_K,SECCOMP_RET_ERRNO|EPERM)
static int iso_query_seccomp(void) {
#if defined(__aarch64__)
#define ISO_QUERY_ARCH AUDIT_ARCH_AARCH64
#elif defined(__x86_64__)
#define ISO_QUERY_ARCH AUDIT_ARCH_X86_64
#else
  return 0;
#endif
#ifdef ISO_QUERY_ARCH
  struct sock_filter rules[]={
    BPF_STMT(BPF_LD|BPF_W|BPF_ABS,offsetof(struct seccomp_data,arch)),
    BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,ISO_QUERY_ARCH,1,0),
    BPF_STMT(BPF_RET|BPF_K,SECCOMP_RET_KILL_PROCESS),
    BPF_STMT(BPF_LD|BPF_W|BPF_ABS,offsetof(struct seccomp_data,nr)),
#ifdef __x86_64__
    BPF_JUMP(BPF_JMP|BPF_JSET|BPF_K,0x40000000,0,1),
    BPF_STMT(BPF_RET|BPF_K,SECCOMP_RET_KILL_PROCESS),
#endif
    /* No IP, packet or netlink sockets, even from deliberately native code. */
    BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,SYS_socket,0,4),
    BPF_STMT(BPF_LD|BPF_W|BPF_ABS,offsetof(struct seccomp_data,args[0])),
    BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,AF_UNIX,1,0),
    BPF_STMT(BPF_RET|BPF_K,SECCOMP_RET_ERRNO|EPERM),
    BPF_STMT(BPF_RET|BPF_K,SECCOMP_RET_ALLOW),
#ifdef SYS_clone3
    /* glibc falls back to clone on ENOSYS; preserve pthread support. */
    BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,SYS_clone3,0,1),
    BPF_STMT(BPF_RET|BPF_K,SECCOMP_RET_ERRNO|ENOSYS),
#endif
    BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,SYS_clone,0,4),
    BPF_STMT(BPF_LD|BPF_W|BPF_ABS,offsetof(struct seccomp_data,args[0])),
    BPF_JUMP(BPF_JMP|BPF_JSET|BPF_K,CLONE_NEWUSER|CLONE_NEWNET|CLONE_NEWNS|CLONE_NEWPID|CLONE_NEWIPC|CLONE_NEWUTS|CLONE_NEWCGROUP|0x80,0,1),
    BPF_STMT(BPF_RET|BPF_K,SECCOMP_RET_ERRNO|EPERM),
    BPF_STMT(BPF_RET|BPF_K,SECCOMP_RET_ALLOW),
    /* The worker may retain dump protection but cannot loosen it. */
    BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,SYS_prctl,0,7),
    BPF_STMT(BPF_LD|BPF_W|BPF_ABS,offsetof(struct seccomp_data,args[0])),
    BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,PR_SET_DUMPABLE,0,4),
    BPF_STMT(BPF_LD|BPF_W|BPF_ABS,offsetof(struct seccomp_data,args[1])),
    BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,0,1,0),
    BPF_STMT(BPF_RET|BPF_K,SECCOMP_RET_ERRNO|EPERM),
    BPF_STMT(BPF_RET|BPF_K,SECCOMP_RET_ALLOW),
    BPF_STMT(BPF_RET|BPF_K,SECCOMP_RET_ERRNO|EPERM),
    ISO_DENY_SYSCALL(SYS_ptrace),
    ISO_DENY_SYSCALL(SYS_process_vm_readv),
    ISO_DENY_SYSCALL(SYS_process_vm_writev),
    ISO_DENY_SYSCALL(SYS_mount), ISO_DENY_SYSCALL(SYS_umount2),
    ISO_DENY_SYSCALL(SYS_pivot_root), ISO_DENY_SYSCALL(SYS_chroot),
    ISO_DENY_SYSCALL(SYS_setns), ISO_DENY_SYSCALL(SYS_unshare),
    ISO_DENY_SYSCALL(SYS_setsid), ISO_DENY_SYSCALL(SYS_setpgid),
    ISO_DENY_SYSCALL(SYS_setuid), ISO_DENY_SYSCALL(SYS_setgid),
    ISO_DENY_SYSCALL(SYS_setresuid), ISO_DENY_SYSCALL(SYS_setresgid),
    ISO_DENY_SYSCALL(SYS_setreuid), ISO_DENY_SYSCALL(SYS_setregid),
    ISO_DENY_SYSCALL(SYS_setgroups), ISO_DENY_SYSCALL(SYS_capset),
    ISO_DENY_SYSCALL(SYS_bpf), ISO_DENY_SYSCALL(SYS_perf_event_open),
    ISO_DENY_SYSCALL(SYS_keyctl), ISO_DENY_SYSCALL(SYS_add_key),
    ISO_DENY_SYSCALL(SYS_request_key), ISO_DENY_SYSCALL(SYS_open_by_handle_at),
#ifdef SYS_io_uring_setup
    ISO_DENY_SYSCALL(SYS_io_uring_setup), ISO_DENY_SYSCALL(SYS_io_uring_enter),
    ISO_DENY_SYSCALL(SYS_io_uring_register),
#endif
    BPF_STMT(BPF_RET|BPF_K,SECCOMP_RET_ALLOW)
  };
  struct sock_fprog program={(unsigned short)(sizeof rules/sizeof rules[0]),rules};
  return prctl(PR_SET_NO_NEW_PRIVS,1,0,0,0)==0 &&
         prctl(PR_SET_SECCOMP,SECCOMP_MODE_FILTER,&program)==0;
#endif
}
static int iso_enter_query_jail(const char *root,uid_t uid) {
  if(geteuid()!=0||uid<20000||uid>60000)return 0;
  if(chdir(root)||chroot(".")||chdir("/"))return 0;
  if(setgroups(0,NULL)||setgid(uid)||setuid(uid))return 0;
  struct __user_cap_header_struct header={_LINUX_CAPABILITY_VERSION_3,0};
  struct __user_cap_data_struct caps[2]={{0},{0}};
  if(syscall(SYS_capset,&header,caps)||getuid()!=uid||geteuid()!=uid||getgid()!=uid)return 0;
  if(!iso_query_limit(RLIMIT_CORE,0)||!iso_query_limit(RLIMIT_FSIZE,0)||
     !iso_query_limit(RLIMIT_NOFILE,64)||!iso_query_limit(RLIMIT_NPROC,32)||
     !iso_query_limit(RLIMIT_AS,(rlim_t)2048*1024*1024))return 0;
  return prctl(PR_SET_DUMPABLE,0)==0 && iso_query_seccomp();
}
#else
static int iso_enter_query_jail(const char *root,uid_t uid) {(void)root;(void)uid;return 0;}
#endif
#endif
