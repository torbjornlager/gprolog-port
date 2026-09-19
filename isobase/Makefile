ROOT ?= $(abspath ..)
.DEFAULT_GOAL := all
export PATH := $(ROOT)/install/bin:$(PATH)
APP ?=
.PHONY: all test diff-test rpc-test https-test compiled-test conformance-test memory-test total-memory-test
total-memory-test: all
	python3 total_memory_tests.py
	python3 memory_tests.py --total-memory-mb 96
memory-test: all
	python3 memory_tests.py
diff-test: all
	python3 differential_tests.py
rpc-test: all
	python3 rpc_tests.py
	python3 rpc_source_tests.py
	python3 https_tests.py
https-test: all
	python3 https_tests.py
all: query-worker query-supervisor isobase-node
isobase-node: http.c protocol.h memory.h memory_tree.h
	$(CC) -std=c11 -Wall -Wextra -Werror -O2 -pthread http.c -o $@
isobase-node-asan: http.c protocol.h memory.h memory_tree.h
	$(CC) -std=c11 -Wall -Wextra -Werror -g -O1 -fsanitize=address,undefined -pthread http.c -o $@
query-supervisor: supervisor.c protocol.h memory.h
	$(CC) -std=c11 -Wall -Wextra -Werror -O2 supervisor.c -o $@
query-supervisor-asan: supervisor.c protocol.h memory.h
	$(CC) -std=c11 -Wall -Wextra -Werror -g -O1 -fsanitize=address,undefined supervisor.c -o $@
query-worker: query.pl source.pl policy.pl prologue.pl text.pl rpc.pl shared_empty.pl terms.c transport.c worker.c protocol.h $(APP)
	$(ROOT)/install/bin/gplc --no-top-level query.pl source.pl policy.pl prologue.pl text.pl rpc.pl shared_empty.pl terms.c transport.c $(APP) worker.c -L -lcurl -L -lpthread -o $@
query-worker-asan: query.pl source.pl policy.pl prologue.pl text.pl rpc.pl shared_empty.pl terms.c transport.c worker.c protocol.h $(APP)
	$(ROOT)/install/bin/gplc --no-top-level query.pl source.pl policy.pl prologue.pl text.pl rpc.pl shared_empty.pl terms.c transport.c $(APP) worker.c -C -fsanitize=address,undefined -L -fsanitize=address,undefined -L -lcurl -L -lpthread -o $@
test: query-worker query-supervisor isobase-node
	python3 tests.py
	python3 source_tests.py
	python3 policy_tests.py
	python3 supervisor_tests.py
	python3 memory_tests.py
	python3 http_tests.py
	python3 total_memory_tests.py
	python3 eviction_tests.py
	python3 request_reader_tests.py
	python3 shared_db_tests.py
	python3 proof_tree_tests.py

shared-compiler: compile_shared.pl compile_shared.c query.pl source.pl policy.pl prologue.pl text.pl rpc.pl shared_empty.pl terms.c transport.c
	$(ROOT)/install/bin/gplc --no-top-level compile_shared.pl query.pl source.pl policy.pl prologue.pl text.pl rpc.pl shared_empty.pl terms.c transport.c compile_shared.c -L -lcurl -L -lpthread -o $@
compiled-test: all shared-compiler
	python3 compiled_tests.py

conformance-test: all
	python3 conformance_tests.py
	python3 differential_tests.py
	python3 endurance_tests.py
