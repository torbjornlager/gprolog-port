#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/wait.h>
#include <signal.h>
#define __GPROLOG_FOREIGN_STRICT__
#include "gprolog.h"

static int interactive;
static void require(int ok, const char *message) {
  if (!ok) { fprintf(stderr, "FAIL: %s\n", message); exit(1); }
}

PlBool gate(int id, PlLong n) {
  if (interactive) {
    char line[64];
    printf("waiting %s %ld\n", Pl_Atom_Name(id), (long)n);
    fflush(stdout);
    require(fgets(line, sizeof line, stdin) != NULL, "resume pipe closed");
    require(strcmp(line, "resume\n") == 0, "invalid resume message");
  }
  return PL_TRUE;
}

static int begin(const char *id, PlTerm args[3]) {
  Pl_Query_Begin(PL_TRUE);
  args[0] = Pl_Mk_Atom(Pl_Create_Atom(id));
  args[1] = Pl_Mk_Variable();
  args[2] = Pl_Mk_Variable();
  return Pl_Query_Call(Pl_Find_Atom("worker"), 3, args);
}

static void solution(const char *id, int n, PlTerm args[3], int status) {
  int functor, arity;
  require(status == PL_SUCCESS, "query did not succeed");
  require(Pl_Rd_Integer_Check(args[1]) == n, "wrong branch");
  PlTerm *fields = Pl_Rd_Compound_Check(args[2], &functor, &arity);
  require(arity == 2 && strcmp(Pl_Atom_Name(functor), "value") == 0,
          "wrong payload shape");
  require(strcmp(Pl_Atom_Name(Pl_Rd_Atom_Check(fields[0])), id) == 0,
          "binding crossed computations");
  require(Pl_Rd_Integer_Check(fields[1]) == n, "payload binding lost");
  printf("solution %s %d\n", id, n);
  fflush(stdout);
}

static void exception_check(void) {
  Pl_Query_Begin(PL_TRUE);
  require(Pl_Query_Call(Pl_Find_Atom("throws"), 0, NULL) == PL_EXCEPTION,
          "exception status lost");
  require(strcmp(Pl_Atom_Name(Pl_Rd_Atom_Check(Pl_Get_Exception())),
                 "probe_exception") == 0, "exception term lost");
  Pl_Query_End(PL_RECOVER);
}

static int runtime(int argc, char **argv, const char *id) {
  PlTerm a[3], b[3];
  Pl_Start_Prolog(argc, argv);
  if (id) {
    solution(id, 1, a, begin(id, a));
    solution(id, 2, a, Pl_Query_Next_Solution());
    require(Pl_Query_Next_Solution() == PL_FAILURE, "cut failed");
    Pl_Query_End(PL_RECOVER);
    exception_check();
    printf("done %s\n", id); fflush(stdout);
  } else {
    solution("a", 1, a, begin("a", a));
    solution("b", 1, b, begin("b", b));
    // There is no query handle to pass here: next always addresses B.
    solution("b", 2, b, Pl_Query_Next_Solution());
    require(Pl_Query_Next_Solution() == PL_FAILURE, "inner cut failed");
    Pl_Query_End(PL_RECOVER);
    solution("a", 2, a, Pl_Query_Next_Solution());
    require(Pl_Query_Next_Solution() == PL_FAILURE, "outer cut failed");
    Pl_Query_End(PL_RECOVER);
    exception_check();
    puts("PASS nested queries: a1 b1 b2 a2 (LIFO)");
  }
  Pl_Stop_Prolog();
  return 0;
}

typedef struct { pid_t pid; FILE *input, *output; } Actor;

static Actor spawn_actor(const char *exe, const char *id, Actor *previous) {
  int to_child[2], from_child[2];
  require(pipe(to_child) == 0 && pipe(from_child) == 0, "pipe");
  pid_t pid = fork(); require(pid >= 0, "fork");
  if (!pid) {
    alarm(20);
    require(dup2(to_child[0], STDIN_FILENO) >= 0, "stdin redirect");
    require(dup2(from_child[1], STDOUT_FILENO) >= 0, "stdout redirect");
    close(to_child[0]); close(to_child[1]);
    close(from_child[0]); close(from_child[1]);
    if (previous) {
      close(fileno(previous->input)); close(fileno(previous->output));
    }
    execl(exe, exe, "child", id, (char *)NULL);
    _exit(127);
  }
  close(to_child[0]); close(from_child[1]);
  Actor a = {pid, fdopen(to_child[1], "w"), fdopen(from_child[0], "r")};
  require(a.input && a.output, "fdopen");
  return a;
}

static void expect(Actor *a, const char *expected) {
  char line[128];
  require(fgets(line, sizeof line, a->output) != NULL, "child exited early");
  require(strcmp(line, expected) == 0, "unexpected child event");
  fputs(line, stdout); fflush(stdout);
}

static void resume(Actor *a) {
  require(fputs("resume\n", a->input) >= 0 && fflush(a->input) == 0, "resume");
}

static void join(Actor *a) {
  int status;
  fclose(a->input); fclose(a->output);
  require(waitpid(a->pid, &status, 0) == a->pid, "waitpid");
  require(WIFEXITED(status) && WEXITSTATUS(status) == 0, "child failed");
}

int main(int argc, char **argv) {
  alarm(20);
  if (argc == 3 && strcmp(argv[1], "child") == 0) {
    interactive = 1;
    // Do not expose controller arguments to GNU Prolog's argument parser.
    return runtime(1, argv, argv[2]);
  }
  if (argc == 2 && strcmp(argv[1], "nested") == 0)
    return runtime(1, argv, NULL);
  require(argc == 2 && strcmp(argv[1], "processes") == 0,
          "usage: controller nested|processes");
  Actor a = spawn_actor(argv[0], "a", NULL);
  Actor b = spawn_actor(argv[0], "b", &a);
  expect(&a, "waiting a 1\n"); expect(&b, "waiting b 1\n");
  resume(&a); expect(&a, "solution a 1\n"); expect(&a, "waiting a 2\n");
  resume(&b); expect(&b, "solution b 1\n"); expect(&b, "waiting b 2\n");
  resume(&a); expect(&a, "solution a 2\n"); expect(&a, "done a\n");
  resume(&b); expect(&b, "solution b 2\n"); expect(&b, "done b\n");
  join(&a); join(&b);
  puts("PASS independent processes: a1 b1 a2 b2 (non-LIFO)");
  return 0;
}
