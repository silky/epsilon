# Makefile for epsilon
#
# Tested on: Mac OS X 10.10.5, Ubuntu 15.04

# Internal directories
src_dir = src
build_dir = build
proto_dir = proto
python_dir = python
sub_dir = epsilon
third_party_dir = third_party
tools_dir = tools
gtest_dir = $(third_party_dir)/googletest/googletest

CC = g++
CXX = g++
OPTFLAGS = -O3

CXXFLAGS = `pkg-config --cflags $(LIBS)`
CXXFLAGS += $(OPTFLAGS) -std=c++14
CXXFLAGS += -Wall -Wextra -Werror -Wno-sign-compare -Wno-unused-parameter
CXXFLAGS += -I$(build_dir) -I$(src_dir) -I$(third_party_dir)
CXXFLAGS += -I$(gtest_dir)/include

LDLIBS += `pkg-config --libs $(LIBS)`

# Platform-specific configuration
UNAME_S = $(shell uname -s)

# Mac OS X
ifeq ($(UNAME_S),Darwin)
# Homebrew gflags doesnt show up in pkg-config
LIBS = protobuf libglog libcurl libtcmalloc libprofiler
CXXFLAGS += -I/usr/local/include
LDLIBS += -L/usr/local/include -lgflags

# glog and protobuf try to define same macros
CXXFLAGS += -Wno-macro-redefined

# Linux
else
LIBS = protobuf libglog libcurl libtcmalloc libprofiler libgflags

# ensure profiler gets linked
LDFLAGS += -Wl,-no-as-needed
endif

common_cc = \
	epsilon/algorithms/prox_admm.cc \
	epsilon/algorithms/prox_admm_test.cc \
	epsilon/algorithms/solver.cc \
	epsilon/expression/expression.cc \
	epsilon/expression/problem.cc \
	epsilon/file/file.cc \
	epsilon/operators/affine.cc \
	epsilon/operators/prox.cc \
	epsilon/operators/prox_test.cc \
	epsilon/parameters/local_parameter_service.cc \
	epsilon/util/dynamic_matrix.cc \
	epsilon/util/string.cc \
	epsilon/util/time.cc \
	epsilon/util/vector.cc \
	epsilon/util/vector_file.cc

common_test_cc = \
	epsilon/algorithms/algorithm_testutil.cc \
	epsilon/expression/expression_testutil.cc \
	epsilon/util/test_main.cc \
	epsilon/util/vector_testutil.cc

proto = \
	epsilon/data.proto \
	epsilon/expression.proto \
	epsilon/prox.proto \
	epsilon/solver_params.proto \
	epsilon/stats.proto \
	epsilon/status.proto

tests = \
	epsilon/algorithms/prox_admm_test \
	epsilon/operators/prox_test \
	epsilon/operators/affine_test \
	epsilon/util/vector_test

# Google test
gtest_srcs = $(gtest_dir)/src/*.cc $(gtest_dir)/src/*.h

# Generated files
proto_cc  = $(proto:%.proto=$(build_dir)/%.pb.cc)
proto_obj = $(proto:%.proto=$(build_dir)/%.pb.o)
proto_py  = $(proto:%.proto=$(python_dir)/%_pb2.py)
common_obj = $(common_cc:%.cc=$(build_dir)/%.o)
common_test_obj = $(common_test_cc:%.cc=$(build_dir)/%.o)
build_tests = $(tests:%=$(build_dir)/%)
build_sub_dirs = $(addprefix $(build_dir)/, $(dir $(common_cc)))

# Stop make from deleting intermediate files
.SECONDARY:

proto_py: $(proto_py)

clean:
	rm -rf $(build_dir) $(python_dir)/build
	find $(python_dir) -name '*_pb2.py*' -or -name '*.pyc' -exec rm {} \;

$(build_dir):
	mkdir -p $(build_sub_dirs)

$(build_dir)/%.pb.cc $(build_dir)/%.pb.h: $(proto_dir)/%.proto | $(build_dir)
	protoc --proto_path=$(proto_dir) --cpp_out=$(build_dir) $<

$(python_dir)/%_pb2.py: $(proto_dir)/%.proto
	protoc --proto_path=$(proto_dir) --python_out=$(python_dir) $<

$(build_dir)/%.pb.o: $(src_dir)/%.pb.cc | $(build_dir)
	$(COMPILE.cc) $(OUTPUT_OPTION) $<

$(build_dir)/%.o: $(src_dir)/%.cc $(proto_cc) | $(build_dir)
	$(COMPILE.cc) $(OUTPUT_OPTION) $<

# Test-related rules
test: $(build_tests) $(proto_py)
	@$(tools_dir)/run_tests.sh $(build_tests)
	@python -m unittest discover $(python_dir)

# NOTE(mwytock): Add -Wno-missing-field-intializers to this rule to avoid error
# on OS X
$(build_dir)/gtest-all.o: $(gtest_srcs)
	$(COMPILE.cc) -I$(gtest_dir) -Wno-missing-field-initializers -c $(gtest_dir)/src/gtest-all.cc -o $@

$(build_dir)/%_test: $(build_dir)/%_test.o $(common_obj) $(proto_obj) $(common_test_obj) $(build_dir)/gtest-all.o
	$(LINK.o) $^ $(LDLIBS) -o $@
