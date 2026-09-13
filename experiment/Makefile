ROOT := $(abspath ..)
export PATH := $(ROOT)/install/bin:$(PATH)

.PHONY: all test
all: controller

controller: probe.pl controller.c
	$(ROOT)/install/bin/gplc --no-top-level probe.pl controller.c -o controller

test: controller
	python3 run_tests.py
