# Makefile for Sphinx documentation

# You can set these variables from the command line.
SPHINXOPTS    ?=
SPHINXBUILD   ?= sphinx-build
PAPER         ?=
BUILDDIR      ?= build

# The 'default' target.
.PHONY: help Makefile

help:
	@$(SPHINXBUILD) -M help "$(CURDIR)/source" "$(CURDIR)/$(BUILDDIR)" $(SPHINXOPTS) $(O)

.PHONY: clean html dirhtml singlehtml pickle json htmlhelp qthelp devhelp epub latex latexpdf text man changes linkcheck doctest gettext

clean:
	rm -rf $(BUILDDIR)

html:
	$(SPHINXBUILD) -b html "$(CURDIR)/source" "$(CURDIR)/$(BUILDDIR)/html" $(SPHINXOPTS) $(O)
	@echo "Build finished. The HTML pages are in $(CURDIR)/$(BUILDDIR)/html."

dirhtml:
	$(SPHINXBUILD) -b dirhtml "$(CURDIR)/source" "$(CURDIR)/$(BUILDDIR)/dirhtml" $(SPHINXOPTS) $(O)
	@echo "Build finished. The HTML pages are in $(CURDIR)/$(BUILDDIR)/dirhtml."

singlehtml:
	$(SPHINXBUILD) -b singlehtml "$(CURDIR)/source" "$(CURDIR)/$(BUILDDIR)/singlehtml" $(SPHINXOPTS) $(O)
	@echo "Build finished. The HTML pages are in $(CURDIR)/$(BUILDDIR)/singlehtml."

pickle:
	$(SPHINXBUILD) -b pickle "$(CURDIR)/source" "$(CURDIR)/$(BUILDDIR)/pickle" $(SPHINXOPTS) $(O)
	@echo "Build finished. The pickle files are in $(CURDIR)/$(BUILDDIR)/pickle."

json:
	$(SPHINXBUILD) -b json "$(CURDIR)/source" "$(CURDIR)/$(BUILDDIR)/json" $(SPHINXOPTS) $(O)
	@echo "Build finished. The HTML pages are in $(CURDIR)/$(BUILDDIR)/json."

htmlhelp:
	$(SPHINXBUILD) -b htmlhelp "$(CURDIR)/source" "$(CURDIR)/$(BUILDDIR)/htmlhelp" $(SPHINXOPTS) $(O)
	@echo "Build finished. The HTML help pages are in $(CURDIR)/$(BUILDDIR)/htmlhelp."

qthelp:
	$(SPHINXBUILD) -b qthelp "$(CURDIR)/source" "$(CURDIR)/$(BUILDDIR)/qthelp" $(SPHINXOPTS) $(O)
	@echo "Build finished. The Qt help pages are in $(CURDIR)/$(BUILDDIR)/qthelp."

devhelp:
	$(SPHINXBUILD) -b devhelp "$(CURDIR)/source" "$(CURDIR)/$(BUILDDIR)/devhelp" $(SPHINXOPTS) $(O)
	@echo "Build finished. The devhelp pages are in $(CURDIR)/$(BUILDDIR)/devhelp."

epub:
	$(SPHINXBUILD) -b epub "$(CURDIR)/source" "$(CURDIR)/$(BUILDDIR)/epub" $(SPHINXOPTS) $(O)
	@echo "Build finished. The epub file is in $(CURDIR)/$(BUILDDIR)/epub."

latex:
	$(SPHINXBUILD) -b latex "$(CURDIR)/source" "$(CURDIR)/$(BUILDDIR)/latex" $(SPHINXOPTS) $(O)
	@echo "Build finished. The latex files are in $(CURDIR)/$(BUILDDIR)/latex."

latexpdf:
	$(SPHINXBUILD) -b latexpdf "$(CURDIR)/source" "$(CURDIR)/$(BUILDDIR)/latex" $(SPHINXOPTS) $(O)
	@echo "Build finished. The pdf files are in $(CURDIR)/$(BUILDDIR)/latex."

text:
	$(SPHINXBUILD) -b text "$(CURDIR)/source" "$(CURDIR)/$(BUILDDIR)/text" $(SPHINXOPTS) $(O)
	@echo "Build finished. The text files are in $(CURDIR)/$(BUILDDIR)/text."

man:
	$(SPHINXBUILD) -b man "$(CURDIR)/source" "$(CURDIR)/$(BUILDDIR)/man" $(SPHINXOPTS) $(O)
	@echo "Build finished. The man pages are in $(CURDIR)/$(BUILDDIR)/man."

changes:
	$(SPHINXBUILD) -b changes "$(CURDIR)/source" "$(CURDIR)/$(BUILDDIR)/changes" $(SPHINXOPTS) $(O)
	@echo "Build finished. The changes file is in $(CURDIR)/$(BUILDDIR)/changes."

linkcheck:
	$(SPHINXBUILD) -b linkcheck "$(CURDIR)/source" "$(CURDIR)/$(BUILDDIR)/linkcheck" $(SPHINXOPTS) $(O)
	@echo "Build finished. The linkcheck results are in $(CURDIR)/$(BUILDDIR)/linkcheck."

doctest:
	$(SPHINXBUILD) -b doctest "$(CURDIR)/source" "$(CURDIR)/$(BUILDDIR)/doctest" $(SPHINXOPTS) $(O)
	@echo "Build finished. The doctest files are in $(CURDIR)/$(BUILDDIR)/doctest."

gettext:
	$(SPHINXBUILD) -b gettext "$(CURDIR)/source" "$(CURDIR)/$(BUILDDIR)/locale" $(SPHINXOPTS) $(O)
	@echo "Build finished. The gettext files are in $(CURDIR)/$(BUILDDIR)/locale."

coverage:
	$(SPHINXBUILD) -b coverage "$(CURDIR)/source" "$(CURDIR)/$(BUILDDIR)/coverage" $(SPHINXOPTS) $(O)
	@echo "Build finished. The coverage files are in $(CURDIR)/$(BUILDDIR)/coverage."

.PHONY: all $(SPHINXBUILD)
all: html
