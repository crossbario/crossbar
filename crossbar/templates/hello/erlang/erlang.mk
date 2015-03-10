###############################################################################
##
##  Copyright (C) 2014, Tavendo GmbH and/or collaborators. All rights reserved.
##
##  Redistribution and use in source and binary forms, with or without
##  modification, are permitted provided that the following conditions are met:
##
##  1. Redistributions of source code must retain the above copyright notice,
##     this list of conditions and the following disclaimer.
##
##  2. Redistributions in binary form must reproduce the above copyright notice,
##     this list of conditions and the following disclaimer in the documentation
##     and/or other materials provided with the distribution.
##
##  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
##  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
##  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
##  ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
##  LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
##  CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
##  SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
##  INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
##  CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
##  ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
##  POSSIBILITY OF SUCH DAMAGE.
##
###############################################################################

# Project.

PROJECT ?= $(notdir $(CURDIR))

# Packages database file.

PKG_FILE ?= $(CURDIR)/.erlang.mk.packages.v1
export PKG_FILE

PKG_FILE_URL ?= https://raw.githubusercontent.com/extend/erlang.mk/master/packages.v1.tsv

define get_pkg_file
	wget --no-check-certificate -O $(PKG_FILE) $(PKG_FILE_URL) || rm $(PKG_FILE)
endef

# Verbosity and tweaks.

V ?= 0

appsrc_verbose_0 = @echo " APP   " $(PROJECT).app.src;
appsrc_verbose = $(appsrc_verbose_$(V))

erlc_verbose_0 = @echo " ERLC  " $(filter %.erl %.core,$(?F));
erlc_verbose = $(erlc_verbose_$(V))

xyrl_verbose_0 = @echo " XYRL  " $(filter %.xrl %.yrl,$(?F));
xyrl_verbose = $(xyrl_verbose_$(V))

dtl_verbose_0 = @echo " DTL   " $(filter %.dtl,$(?F));
dtl_verbose = $(dtl_verbose_$(V))

gen_verbose_0 = @echo " GEN   " $@;
gen_verbose = $(gen_verbose_$(V))

.PHONY: rel clean-rel all clean-all app clean deps clean-deps \
	docs clean-docs build-tests tests build-plt dialyze

# Release.

RELX_CONFIG ?= $(CURDIR)/relx.config

ifneq ($(wildcard $(RELX_CONFIG)),)

RELX ?= $(CURDIR)/relx
export RELX

RELX_URL ?= https://github.com/erlware/relx/releases/download/v1.0.2/relx
RELX_OPTS ?=
RELX_OUTPUT_DIR ?= _rel

ifneq ($(firstword $(subst -o,,$(RELX_OPTS))),)
	RELX_OUTPUT_DIR = $(firstword $(subst -o,,$(RELX_OPTS)))
endif

define get_relx
	wget -O $(RELX) $(RELX_URL) || rm $(RELX)
	chmod +x $(RELX)
endef

rel: clean-rel all $(RELX)
	@$(RELX) -c $(RELX_CONFIG) $(RELX_OPTS)

$(RELX):
	@$(call get_relx)

clean-rel:
	$(gen_verbose) rm -rf $(RELX_OUTPUT_DIR)

endif

# Deps directory.

DEPS_DIR ?= $(CURDIR)/deps
export DEPS_DIR

REBAR_DEPS_DIR = $(DEPS_DIR)
export REBAR_DEPS_DIR

ALL_DEPS_DIRS = $(addprefix $(DEPS_DIR)/,$(DEPS))
ALL_TEST_DEPS_DIRS = $(addprefix $(DEPS_DIR)/,$(TEST_DEPS))

# Application.

ifeq ($(filter $(DEPS_DIR),$(subst :, ,$(ERL_LIBS))),)
ifeq ($(ERL_LIBS),)
	ERL_LIBS = $(DEPS_DIR)
else
	ERL_LIBS := $(ERL_LIBS):$(DEPS_DIR)
endif
endif
export ERL_LIBS

ERLC_OPTS ?= -Werror +debug_info +warn_export_all +warn_export_vars \
	+warn_shadow_vars +warn_obsolete_guard # +bin_opt_info +warn_missing_spec
COMPILE_FIRST ?=
COMPILE_FIRST_PATHS = $(addprefix src/,$(addsuffix .erl,$(COMPILE_FIRST)))

all: deps app

clean-all: clean clean-deps clean-docs
	$(gen_verbose) rm -rf .$(PROJECT).plt $(DEPS_DIR) logs

app: ebin/$(PROJECT).app
	$(eval MODULES := $(shell find ebin -type f -name \*.beam \
		| sed "s/ebin\//'/;s/\.beam/',/" | sed '$$s/.$$//'))
	$(appsrc_verbose) cat src/$(PROJECT).app.src \
		| sed "s/{modules,[[:space:]]*\[\]}/{modules, \[$(MODULES)\]}/" \
		> ebin/$(PROJECT).app

define compile_erl
	$(erlc_verbose) erlc -v $(ERLC_OPTS) -o ebin/ \
		-pa ebin/ -I include/ $(COMPILE_FIRST_PATHS) $(1)
endef

define compile_xyrl
	$(xyrl_verbose) erlc -v -o ebin/ $(1)
	$(xyrl_verbose) erlc $(ERLC_OPTS) -o ebin/ ebin/*.erl
	@rm ebin/*.erl
endef

define compile_dtl
	$(dtl_verbose) erl -noshell -pa ebin/ $(DEPS_DIR)/erlydtl/ebin/ -eval ' \
		Compile = fun(F) -> \
			Module = list_to_atom( \
				string:to_lower(filename:basename(F, ".dtl")) ++ "_dtl"), \
			erlydtl:compile(F, Module, [{out_dir, "ebin/"}]) \
		end, \
		_ = [Compile(F) || F <- string:tokens("$(1)", " ")], \
		init:stop()'
endef

ebin/$(PROJECT).app: $(shell find src -type f -name \*.erl) \
		$(shell find src -type f -name \*.core) \
		$(shell find src -type f -name \*.xrl) \
		$(shell find src -type f -name \*.yrl) \
		$(shell find templates -type f -name \*.dtl 2>/dev/null)
	@mkdir -p ebin/
	$(if $(strip $(filter %.erl %.core,$?)), \
		$(call compile_erl,$(filter %.erl %.core,$?)))
	$(if $(strip $(filter %.xrl %.yrl,$?)), \
		$(call compile_xyrl,$(filter %.xrl %.yrl,$?)))
	$(if $(strip $(filter %.dtl,$?)), \
		$(call compile_dtl,$(filter %.dtl,$?)))

clean:
	$(gen_verbose) rm -rf ebin/ test/*.beam erl_crash.dump

# Dependencies.

define get_dep
	@mkdir -p $(DEPS_DIR)
ifeq (,$(findstring pkg://,$(word 1,$(dep_$(1)))))
	git clone -n -- $(word 1,$(dep_$(1))) $(DEPS_DIR)/$(1)
else
	@if [ ! -f $(PKG_FILE) ]; then $(call get_pkg_file); fi
	git clone -n -- `awk 'BEGIN { FS = "\t" }; \
		$$$$1 == "$(subst pkg://,,$(word 1,$(dep_$(1))))" { print $$$$2 }' \
		$(PKG_FILE)` $(DEPS_DIR)/$(1)
endif
	cd $(DEPS_DIR)/$(1) ; git checkout -q $(word 2,$(dep_$(1)))
endef

define dep_target
$(DEPS_DIR)/$(1):
	$(call get_dep,$(1))
endef

$(foreach dep,$(DEPS),$(eval $(call dep_target,$(dep))))

deps: $(ALL_DEPS_DIRS)
	@for dep in $(ALL_DEPS_DIRS) ; do \
		if [ -f $$dep/Makefile ] ; then \
			$(MAKE) -C $$dep ; \
		else \
			echo "include $(CURDIR)/erlang.mk" | $(MAKE) -f - -C $$dep ; \
		fi ; \
	done

clean-deps:
	@for dep in $(ALL_DEPS_DIRS) ; do \
		if [ -f $$dep/Makefile ] ; then \
			$(MAKE) -C $$dep clean ; \
		else \
			echo "include $(CURDIR)/erlang.mk" | $(MAKE) -f - -C $$dep clean ; \
		fi ; \
	done

# Documentation.

EDOC_OPTS ?=

docs: clean-docs
	$(gen_verbose) erl -noshell \
		-eval 'edoc:application($(PROJECT), ".", [$(EDOC_OPTS)]), init:stop().'

clean-docs:
	$(gen_verbose) rm -f doc/*.css doc/*.html doc/*.png doc/edoc-info

# Tests.

$(foreach dep,$(TEST_DEPS),$(eval $(call dep_target,$(dep))))

TEST_ERLC_OPTS ?= +debug_info +warn_export_vars +warn_shadow_vars +warn_obsolete_guard
TEST_ERLC_OPTS += -DTEST=1 -DEXTRA=1 +'{parse_transform, eunit_autoexport}'

build-test-deps: $(ALL_TEST_DEPS_DIRS)
	@for dep in $(ALL_TEST_DEPS_DIRS) ; do $(MAKE) -C $$dep; done

build-tests: build-test-deps
	$(gen_verbose) erlc -v $(TEST_ERLC_OPTS) -o test/ \
		$(wildcard test/*.erl test/*/*.erl) -pa ebin/

CT_OPTS ?=
CT_RUN = ct_run \
	-no_auto_compile \
	-noshell \
	-pa $(realpath ebin) $(DEPS_DIR)/*/ebin \
	-dir test \
	-logdir logs

CT_SUITES ?=

define test_target
test_$(1): ERLC_OPTS = $(TEST_ERLC_OPTS)
test_$(1): clean deps app build-tests
	@if [ -d "test" ] ; \
	then \
		mkdir -p logs/ ; \
		$(CT_RUN) -suite $(addsuffix _SUITE,$(1)) $(CT_OPTS) ; \
	fi
	$(gen_verbose) rm -f test/*.beam
endef

$(foreach test,$(CT_SUITES),$(eval $(call test_target,$(test))))

tests: ERLC_OPTS = $(TEST_ERLC_OPTS)
tests: clean deps app build-tests
	@if [ -d "test" ] ; \
	then \
		mkdir -p logs/ ; \
		$(CT_RUN) -suite $(addsuffix _SUITE,$(CT_SUITES)) $(CT_OPTS) ; \
	fi
	$(gen_verbose) rm -f test/*.beam

# Dialyzer.

DIALYZER_PLT ?= $(CURDIR)/.$(PROJECT).plt
export DIALYZER_PLT

PLT_APPS ?=
DIALYZER_OPTS ?= -Werror_handling -Wrace_conditions \
	-Wunmatched_returns # -Wunderspecs

build-plt: deps app
	@dialyzer --build_plt --apps erts kernel stdlib $(PLT_APPS) $(ALL_DEPS_DIRS)

dialyze:
	@dialyzer --src src --no_native $(DIALYZER_OPTS)

# Packages.

$(PKG_FILE):
	@$(call get_pkg_file)

pkg-list: $(PKG_FILE)
	@cat $(PKG_FILE) | awk 'BEGIN { FS = "\t" }; { print \
		"Name:\t\t" $$1 "\n" \
		"Repository:\t" $$2 "\n" \
		"Website:\t" $$3 "\n" \
		"Description:\t" $$4 "\n" }'

ifdef q
pkg-search: $(PKG_FILE)
	@cat $(PKG_FILE) | grep -i ${q} | awk 'BEGIN { FS = "\t" }; { print \
		"Name:\t\t" $$1 "\n" \
		"Repository:\t" $$2 "\n" \
		"Website:\t" $$3 "\n" \
		"Description:\t" $$4 "\n" }'
else
pkg-search:
	@echo "Usage: make pkg-search q=STRING"
endif
