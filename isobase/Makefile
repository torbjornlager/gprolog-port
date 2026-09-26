ROOT ?= $(abspath ..)
.DEFAULT_GOAL := all
export PATH := $(ROOT)/install/bin:$(PATH)
APP ?=
.PHONY: all test credentials-test outbound-test boundary-contract-test status-check comparison-check contract-test security-test diff-test rpc-test https-test compiled-test conformance-test memory-test total-memory-test
status-check:
	python3 boundary_decisions_tests.py
	python3 predicate_inventory.py --check
	python3 status_report.py --check
	python3 status_report_tests.py
boundary-contract-test: all
	python3 boundary_contract_tests.py
comparison-check: all
	python3 comparison_config.py --strict-environment
contract-test: all status-check
	python3 comparison_config_tests.py
	python3 contract_tests.py
outbound-test: all
	python3 outbound_socket_tests.py
	python3 outbound_policy_tests.py
credentials-test: all
	python3 outbound_credentials_tests.py
security-test: all outbound-test credentials-test
	python3 security_tests.py
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
	python3 rpc_address_tests.py
	python3 https_tests.py
https-test: all
	python3 https_tests.py
all: query-worker query-supervisor isobase-node
isobase-node: http.c http_security.h protocol.h memory.h memory_tree.h
	$(CC) -std=c11 -Wall -Wextra -Werror -O2 -pthread http.c -o $@
isobase-node-asan: http.c http_security.h protocol.h memory.h memory_tree.h
	$(CC) -std=c11 -Wall -Wextra -Werror -g -O1 -fsanitize=address,undefined -pthread http.c -o $@
query-supervisor: supervisor.c protocol.h memory.h
	$(CC) -std=c11 -Wall -Wextra -Werror -O2 supervisor.c -o $@
query-supervisor-asan: supervisor.c protocol.h memory.h
	$(CC) -std=c11 -Wall -Wextra -Werror -g -O1 -fsanitize=address,undefined supervisor.c -o $@
query-worker: query.pl source.pl policy.pl prologue.pl text.pl rpc.pl shared_empty.pl terms.c transport.c outbound_policy.h outbound_credentials.h worker.c protocol.h $(APP)
	$(ROOT)/install/bin/gplc --no-top-level query.pl source.pl policy.pl prologue.pl text.pl rpc.pl shared_empty.pl terms.c transport.c $(APP) worker.c -L -lcurl -L -lpthread -o $@
query-worker-asan: query.pl source.pl policy.pl prologue.pl text.pl rpc.pl shared_empty.pl terms.c transport.c outbound_policy.h outbound_credentials.h worker.c protocol.h $(APP)
	$(ROOT)/install/bin/gplc --no-top-level query.pl source.pl policy.pl prologue.pl text.pl rpc.pl shared_empty.pl terms.c transport.c $(APP) worker.c -C -fsanitize=address,undefined -L -fsanitize=address,undefined -L -lcurl -L -lpthread -o $@
test: query-worker query-supervisor isobase-node
	python3 comparison_config_tests.py
	python3 tests.py
	python3 source_tests.py
	python3 policy_tests.py
	python3 numeric_contract_tests.py
	python3 rpc_address_tests.py
	python3 supervisor_tests.py
	python3 memory_tests.py
	python3 security_tests.py
	python3 outbound_socket_tests.py
	python3 outbound_policy_tests.py
	python3 outbound_credentials_tests.py
	python3 http_tests.py
	python3 total_memory_tests.py
	python3 eviction_tests.py
	python3 request_reader_tests.py
	python3 shared_db_tests.py
	python3 proof_tree_tests.py

shared-compiler: compile_shared.pl compile_shared.c query.pl source.pl policy.pl prologue.pl text.pl rpc.pl shared_empty.pl terms.c transport.c outbound_policy.h outbound_credentials.h
	$(ROOT)/install/bin/gplc --no-top-level compile_shared.pl query.pl source.pl policy.pl prologue.pl text.pl rpc.pl shared_empty.pl terms.c transport.c compile_shared.c -L -lcurl -L -lpthread -o $@
compiled-test: all shared-compiler
	python3 compiled_tests.py

conformance-test: all contract-test
	python3 conformance_tests.py
	python3 differential_tests.py
	python3 endurance_tests.py
