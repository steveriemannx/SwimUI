PYTHON ?= python3
SWIM   := ./bin/Swim
ROOT   := $(shell pwd)

.PHONY: help test test-binding test-all test-update examples check clean version \
        ffi ffi-release demo demo-snapshot binding-scene

help:
	@echo "make test           run the Swim test suite"
	@echo "make test-binding   run the end-to-end test of the FerroUI binding"
	@echo "make test-all       both suites"
	@echo "make test-update    regenerate expected outputs"
	@echo "make examples       run all example programs"
	@echo "make check          compile-check all examples, tests and examples/ui/"
	@echo "make ffi            build the Rust bridge (debug)"
	@echo "make ffi-release    build the Rust bridge (optimised)"
	@echo "make demo           build and run the SwimUI demo"
	@echo "make demo-snapshot  write examples/ui/shots/demo.png and quit"
	@echo "make binding-scene  run the scripted view-layer scene"
	@echo "make clean          clean caches and generated files"
	@echo "make version        print the compiler version"

test:
	$(PYTHON) tests/run_tests.py

test-binding:
	$(PYTHON) tests/binding_test.py

test-all: test test-binding

test-update:
	$(PYTHON) tests/run_tests.py --update

examples:
	@for f in examples/*.sw examples/programs/*.sw; do \
		printf '%-42s' "$$f"; \
		if $(SWIM) run "$$f" >/dev/null 2>&1; then echo OK; else echo FAIL; fi; \
	done

check:
	@for f in examples/*.sw examples/programs/*.sw tests/cases/*.sw \
		tests/projects/*/main.sw; do \
		$(SWIM) check "$$f" >/dev/null || exit 1; \
	done
	@export SWIM_PATH="$(ROOT)/examples/ui" ; \
	for f in examples/ui/*.sw tests/binding/*.sw; do \
		$(SWIM) check "$$f" >/dev/null || exit 1; \
	done
	@echo "all examples, tests and examples/ui programs type-check"

ffi:
	./scripts/build-ffi.sh

ffi-release:
	./scripts/build-ffi.sh --release

demo:
	./scripts/run-demo.sh

demo-snapshot:
	./scripts/run-demo.sh --snapshot examples/ui/shots/demo.png

binding-scene:
	./scripts/run-demo.sh --program tests/binding/SwimUITest.sw \
		--snapshot build/scene.png

clean:
	rm -rf .Swim-cache __pycache__ src/swimc/__pycache__ tests/__pycache__
	rm -f examples/*.c examples/programs/*.c
	find . -name '*.pyc' -delete
	rm -rf build/test build/demo build/smoke.png build/scene.png

version:
	$(SWIM) version
