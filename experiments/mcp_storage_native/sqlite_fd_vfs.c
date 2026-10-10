/* Research only. SQLite public-domain headers; this component follows repo MIT.
 * Audited upstream: SQLite 3.50.4 os_unix.c and pager.c. No libsqlite3 link.
 * No claim of protection against post-pin aliases or hostile crash removal.
 */
#define _GNU_SOURCE
#include "include/sqlite3ext.h"
SQLITE_EXTENSION_INIT1
#include <sys/stat.h>
#include <sys/mman.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

static sqlite3_vfs *unix_vfs;
static sqlite3_vfs vfs;
static int dbfd=-1, journalfd=-1, dirfd=-1, lock_level=0;
static int known[128], kinds[128], sync_count=0, bound=0;
static int denied_count=0;
static int close_error_count=0, last_close_errno=0, close_call_count=0, close_fault_used=0;
static const char *main_name="/spike/main";
static const char *journal_name="/spike/main-journal";

static void trace(const char *event, int value){
  fprintf(stderr,"{\"event\":\"%s\",\"value\":%d,\"lock\":%d}\n",event,value,lock_level);
  fflush(stderr);
}
static int deny(const char *what){ denied_count++; trace(what,0); errno=EPERM; return -1; }
static int kind(int fd){
  for(int i=0;i<128;i++) if(known[i]==fd+1) return kinds[i];
  return 0;
}
/* Fault primitive returns EIO without recording status or poisoning context.
 * Model Linux's released-FD error case; the observer must latch actual results.
 * Never retry close() after an error.
 */
static int close_syscall(int fd,int k){
  const char *fault=getenv("SPIKE_CLOSE_EIO_KIND");
  if(!close_fault_used && fault && atoi(fault)==k){
    close_fault_used=1;
    int rc=close(fd);
    if(rc!=0) return rc;
    errno=EIO; return -1;
  }
  return close(fd);
}
static int observed_close(int fd,int k){
  int rc=close_syscall(fd,k), saved=rc<0?errno:0;
  close_call_count++;
  if(rc<0){ close_error_count++; last_close_errno=saved; }
  fprintf(stderr,"{\"event\":\"close_syscall_result\",\"fd\":%d,\"kind\":%d,\"call\":%d,\"result\":%d,\"errno\":%d,\"lock\":%d}\n",
    fd,k,close_call_count,rc,saved,lock_level);
  fflush(stderr); errno=saved; return rc;
}
static int remember(int fd, int k){
  if(fd<0) return fd;
  for(int i=0;i<128;i++) if(!known[i]){ known[i]=fd+1; kinds[i]=k; return fd; }
  observed_close(fd,k); return deny("descriptor_budget_denied");
}
static int selected(const char *name){
  if(!name) return -1;
  if(!strcmp(name,main_name)) return dbfd;
  if(!strcmp(name,journal_name)) return journalfd;
  return -1;
}
static int writable(int fd){
  struct stat st;
  if(denied_count) return deny("poisoned_context_write_denied");
  if(close_error_count) return deny("close_failure_write_denied");
  if(kind(fd)!=1 && kind(fd)!=2) return deny("unknown_write_fd_denied");
  if(lock_level!=SQLITE_LOCK_EXCLUSIVE) return deny("write_without_exclusive_denied");
  /* A detector, NOT an atomic no-external-alias guarantee. */
  if(fstat(fd,&st) || st.st_nlink!=1) return deny("link_count_write_denied");
  return 0;
}
static int h_open(const char *name,int flags,int mode){
  (void)mode;
  int fd=selected(name);
  trace("unix_open",flags);
  int allowed=O_ACCMODE|O_CREAT|O_CLOEXEC|O_NOFOLLOW|O_LARGEFILE;
  if(fd<0 || (flags & ~allowed) || (flags & O_ACCMODE)==O_WRONLY)
    return deny("unknown_or_destructive_open_denied");
  return remember(fcntl(fd,F_DUPFD_CLOEXEC,3),fd==dbfd?1:2);
}
static int h_close(int fd){
  int k=kind(fd);
  if(!k) return deny("unknown_close_denied");
  trace("unix_close",fd);
  for(int i=0;i<128;i++) if(known[i]==fd+1){ known[i]=0; kinds[i]=0; }
  return observed_close(fd,k);
}
static int h_access(const char *name,int mode){
  (void)mode; trace("unix_access",0);
  if(selected(name)<0) return deny("unknown_access_denied");
  return 0;
}
static int h_stat(const char *name,struct stat *st){
  int fd=selected(name); trace("unix_stat",0);
  if(fd<0) return deny("unknown_stat_denied");
  return fstat(fd,st);
}
static int h_fstat(int fd,struct stat *st){
  if(!kind(fd)) return deny("unknown_fstat_denied");
  return fstat(fd,st);
}
static int h_truncate(int fd,off_t size){
  trace("unix_truncate",(int)size);
  if(writable(fd)) return -1;
  return ftruncate(fd,size);
}
static int h_fcntl(int fd,int cmd,...){
  if(!kind(fd)) return deny("unknown_fcntl_denied");
  trace("unix_fcntl",cmd);
  va_list ap; va_start(ap,cmd); int rc;
  if(cmd==F_SETLK || cmd==F_SETLKW || cmd==F_GETLK){
    struct flock *arg=va_arg(ap,struct flock*);
    fprintf(stderr,"{\"event\":\"posix_lock\",\"command\":%d,\"type\":%d,\"start\":%lld,\"length\":%lld,\"lock\":%d}\n",
      cmd,(int)arg->l_type,(long long)arg->l_start,(long long)arg->l_len,lock_level);
    fflush(stderr); rc=fcntl(fd,cmd,arg);
  }else if(cmd==F_GETFD || cmd==F_GETFL){ rc=fcntl(fd,cmd);
  }else if(cmd==F_SETFD){ int arg=va_arg(ap,int); rc=fcntl(fd,cmd,arg);
  }else{ rc=deny("unknown_fcntl_command_denied"); }
  va_end(ap); return rc;
}
static ssize_t h_read(int fd,void *p,size_t n){
  if(!kind(fd)) return deny("unknown_read_denied"); return read(fd,p,n);
}
static ssize_t h_pread(int fd,void *p,size_t n,off_t off){
  if(!kind(fd)) return deny("unknown_pread_denied"); return pread(fd,p,n,off);
}
static void before_write(int fd){
  trace(kind(fd)==1?"db_write_attempt":"journal_write_attempt",(int)fd);
  if(kind(fd)==1 && getenv("SPIKE_PAUSE_DB_WRITE")){
    unsetenv("SPIKE_PAUSE_DB_WRITE");
    puts("{\"checkpoint\":\"native_before_db_write\"}"); fflush(stdout);
    char line[32]; if(!fgets(line,sizeof(line),stdin) || strcmp(line,"continue\n")) _exit(87);
  }
}
static void write_result(int fd,size_t n,ssize_t rc,int saved,int performed){
  fprintf(stderr,"{\"event\":\"write_syscall_result\",\"fd\":%d,\"kind\":%d,\"requested_bytes\":%zu,\"result_bytes\":%lld,\"errno\":%d,\"syscall_performed\":%s,\"lock\":%d}\n",
    fd,kind(fd),n,(long long)rc,saved,performed?"true":"false",lock_level);
  fflush(stderr); errno=saved;
}
static ssize_t h_write(int fd,const void *p,size_t n){
  before_write(fd);
  int performed=writable(fd)==0;
  ssize_t rc=performed?write(fd,p,n):-1; int saved=rc<0?errno:0;
  write_result(fd,n,rc,saved,performed);
  if(kind(fd)==1 && getenv("SPIKE_CRASH_DB_WRITE")) _exit(86);
  return rc;
}
static ssize_t h_pwrite(int fd,const void *p,size_t n,off_t off){
  before_write(fd);
  int performed=writable(fd)==0;
  ssize_t rc=performed?pwrite(fd,p,n,off):-1; int saved=rc<0?errno:0;
  write_result(fd,n,rc,saved,performed);
  if(kind(fd)==1 && getenv("SPIKE_CRASH_DB_WRITE")) _exit(86);
  return rc;
}
static int h_chmod(int fd,mode_t mode){ (void)fd;(void)mode; return deny("chmod_denied"); }
static int h_chown(int fd,uid_t uid,gid_t gid){ (void)fd;(void)uid;(void)gid; return deny("chown_denied"); }
static int h_allocate(int fd,off_t off,off_t len){
  if(writable(fd)) return EPERM; trace("unix_allocate",(int)len); return posix_fallocate(fd,off,len);
}
static int h_unlink(const char *name){ (void)name; return deny("unlink_denied"); }
static int h_mkdir(const char *name,mode_t mode){ (void)name;(void)mode; return deny("mkdir_denied"); }
static int h_rmdir(const char *name){ (void)name; return deny("rmdir_denied"); }
static char *h_getcwd(char *p,size_t n){ (void)p;(void)n; deny("getcwd_denied"); return NULL; }
static ssize_t h_readlink(const char *name,char *p,size_t n){
  (void)name;(void)p;(void)n; return deny("readlink_denied");
}
static int h_directory(const char *name,int *out){
  /* Never resolve an input path: only recognized names use the inherited FD. */
  if(selected(name)<0){ *out=-1; deny("unknown_directory_denied"); return SQLITE_CANTOPEN; }
  trace("directory_sync_descriptor",dirfd);
  *out=remember(fcntl(dirfd,F_DUPFD_CLOEXEC,3),3);
  return *out<0?SQLITE_CANTOPEN:SQLITE_OK;
}
static void *h_mmap(void *p,size_t n,int prot,int flags,int fd,off_t off){
  (void)p;(void)n;(void)prot;(void)flags;(void)fd;(void)off;
  deny("mmap_denied"); return MAP_FAILED;
}
static int h_munmap(void *p,size_t n){ (void)p;(void)n; return deny("munmap_denied"); }
static void *h_mremap(void *p,size_t old,size_t n,int flags,...){
  (void)p;(void)old;(void)n;(void)flags; deny("mremap_denied"); return MAP_FAILED;
}

typedef struct { sqlite3_file base; sqlite3_file *inner; int type; } SpFile;
#define INNER(f) (((SpFile*)(f))->inner)
static int io_close(sqlite3_file *f){
  trace("vfs_close",0); int rc=INNER(f)->pMethods->xClose(INNER(f)); sqlite3_free(INNER(f));
  trace("vfs_close_result",rc);
  return rc;
}
static int io_read(sqlite3_file *f,void *p,int n,sqlite3_int64 off){ return INNER(f)->pMethods->xRead(INNER(f),p,n,off); }
static int io_write(sqlite3_file *f,const void *p,int n,sqlite3_int64 off){ return INNER(f)->pMethods->xWrite(INNER(f),p,n,off); }
static int io_truncate(sqlite3_file *f,sqlite3_int64 size){ return INNER(f)->pMethods->xTruncate(INNER(f),size); }
static int io_sync(sqlite3_file *f,int flags){
  trace("vfs_sync",++sync_count);
  const char *fault=getenv("SPIKE_FAIL_SYNC");
  if(fault && atoi(fault)==sync_count){ trace("injected_sync_failure",sync_count); return SQLITE_IOERR_FSYNC; }
  int rc=INNER(f)->pMethods->xSync(INNER(f),flags); trace("vfs_sync_result",rc); return rc;
}
static int io_size(sqlite3_file *f,sqlite3_int64 *size){ return INNER(f)->pMethods->xFileSize(INNER(f),size); }
static int io_lock(sqlite3_file *f,int level){
  int rc=INNER(f)->pMethods->xLock(INNER(f),level);
  if(rc==SQLITE_OK) lock_level=level; trace("vfs_lock_result",rc); trace("vfs_lock_level",level); return rc;
}
static int io_unlock(sqlite3_file *f,int level){
  int rc=INNER(f)->pMethods->xUnlock(INNER(f),level);
  if(rc==SQLITE_OK) lock_level=level; trace("vfs_unlock_result",rc); return rc;
}
static int io_reserved(sqlite3_file *f,int *out){ return INNER(f)->pMethods->xCheckReservedLock(INNER(f),out); }
static int io_control(sqlite3_file *f,int op,void *arg){ return INNER(f)->pMethods->xFileControl(INNER(f),op,arg); }
static int io_sector(sqlite3_file *f){ return INNER(f)->pMethods->xSectorSize(INNER(f)); }
static int io_device(sqlite3_file *f){ return INNER(f)->pMethods->xDeviceCharacteristics(INNER(f)); }
static int io_shmmap(sqlite3_file *f,int p,int n,int extend,void volatile **out){
  (void)f;(void)p;(void)n;(void)extend;(void)out; deny("unexpected_shm_map_denied"); return SQLITE_IOERR_SHMMAP;
}
static int io_shmlock(sqlite3_file *f,int off,int n,int flags){
  (void)f;(void)off;(void)n;(void)flags; deny("unexpected_shm_lock_denied"); return SQLITE_IOERR_SHMLOCK;
}
static void io_shmbarrier(sqlite3_file *f){ (void)f; trace("unexpected_shm_barrier_fatal",0); _exit(88); }
static int io_shmunmap(sqlite3_file *f,int flag){ (void)f;(void)flag; deny("unexpected_shm_unmap_denied"); return SQLITE_IOERR_SHMMAP; }
static const sqlite3_io_methods methods={2,io_close,io_read,io_write,io_truncate,io_sync,io_size,
  io_lock,io_unlock,io_reserved,io_control,io_sector,io_device,
  io_shmmap,io_shmlock,io_shmbarrier,io_shmunmap,NULL,NULL};
static int v_open(sqlite3_vfs *v,const char *name,sqlite3_file *f,int flags,int *out){
  (void)v; f->pMethods=NULL; trace("vfs_open",flags);
  int type=flags&0x0fff00;
  if(!bound || selected(name)<0 || (type!=SQLITE_OPEN_MAIN_DB && type!=SQLITE_OPEN_MAIN_JOURNAL)){
    trace("file_kind_denied",type); deny("file_kind_context_poisoned"); return SQLITE_CANTOPEN;
  }
  SpFile *sp=(SpFile*)f; sp->type=type; sp->inner=sqlite3_malloc(unix_vfs->szOsFile);
  if(!sp->inner) return SQLITE_NOMEM;
  memset(sp->inner,0,unix_vfs->szOsFile);
  int rc=unix_vfs->xOpen(unix_vfs,name,sp->inner,flags,out);
  if(rc!=SQLITE_OK){
    if(sp->inner->pMethods) sp->inner->pMethods->xClose(sp->inner);
    sqlite3_free(sp->inner); return rc;
  }
  f->pMethods=&methods; return SQLITE_OK;
}
static int v_full(sqlite3_vfs *v,const char *name,int n,char *out){
  (void)v;
  if(!name || strcmp(name,main_name) || n<12){ deny("full_path_denied"); return SQLITE_CANTOPEN; }
  strcpy(out,main_name); return SQLITE_OK;
}
static int v_delete(sqlite3_vfs *v,const char *name,int sync){
  (void)v;(void)name;(void)sync; deny("vfs_delete_denied"); return SQLITE_IOERR_DELETE;
}
static int v_access(sqlite3_vfs *v,const char *name,int flags,int *out){
  (void)v;(void)flags;
  /* Known rollback-only probes, not permission to open either object. */
  if(name && (!strcmp(name,"/spike/main-wal") || !strcmp(name,"/spike/main-shm"))){
    *out=0; trace("rollback_sidecar_absence_probe",0); return SQLITE_OK;
  }
  if(selected(name)<0){ *out=0; deny("unknown_vfs_access_denied"); return SQLITE_IOERR_ACCESS; }
  *out=1; return SQLITE_OK;
}
static void *v_dlopen(sqlite3_vfs *v,const char *name){
  (void)v;(void)name; deny("additional_extension_denied"); return NULL;
}

struct Hook { const char *name; sqlite3_syscall_ptr fn; };
#define H(name,fn) {name,(sqlite3_syscall_ptr)fn}
static struct Hook hooks[]={H("open",h_open),H("close",h_close),H("access",h_access),
  H("getcwd",h_getcwd),H("stat",h_stat),H("fstat",h_fstat),H("ftruncate",h_truncate),
  H("fcntl",h_fcntl),H("read",h_read),H("pread",h_pread),H("pread64",h_pread),
  H("write",h_write),H("pwrite",h_pwrite),H("pwrite64",h_pwrite),H("fchmod",h_chmod),
  H("fallocate",h_allocate),H("unlink",h_unlink),H("openDirectory",h_directory),
  H("mkdir",h_mkdir),H("rmdir",h_rmdir),H("fchown",h_chown),H("geteuid",geteuid),
  H("mmap",h_mmap),H("munmap",h_munmap),H("mremap",h_mremap),H("getpagesize",getpagesize),
  H("readlink",h_readlink),H("lstat",h_stat)};
static void profile(sqlite3_context *ctx,int argc,sqlite3_value **argv){
  (void)argc;(void)argv; char result[2048]="";
  const char *name=NULL;
  if(!unix_vfs || unix_vfs->iVersion<3 || !unix_vfs->xNextSystemCall){ sqlite3_result_error(ctx,"unix profile unavailable",-1); return; }
  while((name=unix_vfs->xNextSystemCall(unix_vfs,name))){
    if(strlen(result)+strlen(name)+2>=sizeof(result)){ sqlite3_result_error(ctx,"profile overflow",-1); return; }
    if(*result) strcat(result,","); strcat(result,name);
  }
  sqlite3_result_text(ctx,result,-1,SQLITE_TRANSIENT);
}
static void status(sqlite3_context *ctx,int argc,sqlite3_value **argv){
  (void)argc;(void)argv; sqlite3_result_int(ctx,denied_count);
}
static void close_status(sqlite3_context *ctx,int argc,sqlite3_value **argv){
  (void)argc;(void)argv; sqlite3_result_int(ctx,close_error_count);
}
static void close_errno(sqlite3_context *ctx,int argc,sqlite3_value **argv){
  (void)argc;(void)argv; sqlite3_result_int(ctx,last_close_errno);
}
static void probes(sqlite3_context *ctx,int argc,sqlite3_value **argv){
  (void)argc;(void)argv; int out=0; void volatile *mapping=NULL;
  h_open("/proc/self/fd/1",O_WRONLY,0);
  v_access(&vfs,"/unselected/foreign",SQLITE_ACCESS_EXISTS,&out);
  v_delete(&vfs,journal_name,1);
  io_shmmap(NULL,0,4096,1,&mapping);
  io_shmlock(NULL,0,1,SQLITE_SHM_LOCK);
  h_mmap(NULL,4096,PROT_READ,MAP_SHARED,dbfd,0);
  h_directory("/unselected/foreign",&out);
  sqlite3_result_int(ctx,denied_count);
}
static void bind_fds(sqlite3_context *ctx,int argc,sqlite3_value **argv){
  (void)argc;
  if(bound || sizeof(off_t)!=8 || sizeof(void*)!=8 || strcmp(sqlite3_libversion(),"3.50.4") ||
     !unix_vfs || unix_vfs->iVersion<3 || !unix_vfs->xSetSystemCall || !unix_vfs->xGetSystemCall){
    sqlite3_result_error(ctx,"unsupported or repeated binding",-1); return;
  }
  dbfd=sqlite3_value_int(argv[0]); journalfd=sqlite3_value_int(argv[1]); dirfd=sqlite3_value_int(argv[2]);
  struct stat db,jr,dir;
  if(dbfd<3 || journalfd<3 || dirfd<3 || dbfd==journalfd || dbfd==dirfd || journalfd==dirfd ||
     fstat(dbfd,&db) || fstat(journalfd,&jr) || fstat(dirfd,&dir) ||
     !S_ISREG(db.st_mode) || !S_ISREG(jr.st_mode) || !S_ISDIR(dir.st_mode) ||
     db.st_nlink!=1 || jr.st_nlink!=1 || db.st_size>4*1024*1024 || jr.st_size>4*1024*1024 ||
     db.st_dev!=dir.st_dev || jr.st_dev!=dir.st_dev || (db.st_dev==jr.st_dev && db.st_ino==jr.st_ino)){
    sqlite3_result_error(ctx,"invalid inherited objects",-1); return;
  }
  unsigned char header[20];
  if(pread(dbfd,header,20,0)!=20 || header[18]!=1 || header[19]!=1){
    sqlite3_result_error(ctx,"WAL or non-rollback database unsupported",-1); return;
  }
  const char *name=NULL;
  while((name=unix_vfs->xNextSystemCall(unix_vfs,name))){
    unsigned i; for(i=0;i<sizeof(hooks)/sizeof(hooks[0]);i++) if(!strcmp(hooks[i].name,name)) break;
    if(i==sizeof(hooks)/sizeof(hooks[0])){ sqlite3_result_error(ctx,"unreviewed syscall present",-1); return; }
  }
  for(unsigned i=0;i<sizeof(hooks)/sizeof(hooks[0]);i++){
    if(unix_vfs->xGetSystemCall(unix_vfs,hooks[i].name) &&
       unix_vfs->xSetSystemCall(unix_vfs,hooks[i].name,hooks[i].fn)!=SQLITE_OK){
      sqlite3_result_error(ctx,"hook installation failed; worker must exit",-1); return;
    }
    if(unix_vfs->xGetSystemCall(unix_vfs,hooks[i].name)){
      fprintf(stderr,"{\"event\":\"hook_installed\",\"name\":\"%s\",\"lock\":0}\n",hooks[i].name);
      fflush(stderr);
    }
  }
  vfs=*unix_vfs; vfs.zName="docatlas_spike"; vfs.pNext=NULL;
  vfs.szOsFile=sizeof(SpFile); vfs.xOpen=v_open; vfs.xFullPathname=v_full;
  vfs.xDelete=v_delete; vfs.xAccess=v_access;
  vfs.xDlOpen=v_dlopen;
  int rc=sqlite3_vfs_register(&vfs,0);
  if(rc!=SQLITE_OK){ sqlite3_result_error(ctx,"VFS registration failed",-1); return; }
  bound=1; trace("inherited_binding_complete",0); sqlite3_result_int(ctx,1);
}
#ifdef _WIN32
__declspec(dllexport)
#endif
int sqlite3_extension_init(sqlite3 *db,char **error,const sqlite3_api_routines *api){
  (void)error; SQLITE_EXTENSION_INIT2(api); unix_vfs=sqlite3_vfs_find("unix");
  int rc=sqlite3_create_function(db,"spike_profile",0,SQLITE_UTF8,NULL,profile,NULL,NULL);
  if(rc==SQLITE_OK) rc=sqlite3_create_function(db,"spike_status",0,SQLITE_UTF8,NULL,status,NULL,NULL);
  if(rc==SQLITE_OK) rc=sqlite3_create_function(db,"spike_close_errors",0,SQLITE_UTF8,NULL,close_status,NULL,NULL);
  if(rc==SQLITE_OK) rc=sqlite3_create_function(db,"spike_close_errno",0,SQLITE_UTF8,NULL,close_errno,NULL,NULL);
  if(rc==SQLITE_OK) rc=sqlite3_create_function(db,"spike_probes",0,SQLITE_UTF8,NULL,probes,NULL,NULL);
  if(rc==SQLITE_OK) rc=sqlite3_create_function(db,"spike_bind",3,SQLITE_UTF8,NULL,bind_fds,NULL,NULL);
  /* VFS and syscall callbacks remain registered until this worker exits. */
  return rc==SQLITE_OK ? SQLITE_OK_LOAD_PERMANENTLY : rc;
}
