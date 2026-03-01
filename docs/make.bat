@ECHO OFF

REM Command file for Sphinx documentation

if "%SPHINXBUILD%" == "" (
	set SPHINXBUILD=sphinx-build
)
set BUILDDIR=build
set ALLSPHINXOPTS=-d %BUILDDIR%/doctrees %SPHINXOPTS% source
set I18NSPHINXOPTS=%ALLSPHINXOPTS%
if NOT "%PAPER%" == "" (
	set ALLSPHINXOPTS=-D latex_paper_size=%PAPER% %ALLSPHINXOPTS%
	set I18NSPHINXOPTS=-D latex_paper_size=%PAPER% %I18NSPHINXOPTS%
)

if "%1" == "" goto help

if "%1" == "help" (
	:help
	echo.Please use `make [target]` where [target] is one of
	echo.  html       to make standalone HTML files
	echo.  dirhtml    to make HTML files named index.html in directories
	echo.  singlehtml to make single-file HTML documentation
	echo.  pickle     to make pickle files
	echo.  json       to make JSON files
	echo.  htmlhelp   to make HTML files and a HTML help project
	echo.  qthelp     to make HTML files and a qthelp project
	echo.  devhelp    to make HTML files and a Devhelp project
	echo.  epub       to make an epub file
	echo.  latex      to make LaTeX files, you can set PAPER=a4 or PAPER=letter
	echo.  text       to make text files
	echo.  man        to make manual pages
	echo.  texinfo    to make Texinfo files
	echo.  gettext    to make PO message catalogs
	echo.  changes    to make an overview of all changed/added/deprecated items
	echo.  xml        to make Docutils-native XML files
	echo.  pseudoxml  to make pseudoxml-ified files for display purposes
	echo.  linkcheck  to make a link check of all external links
	echo.  doctest    to make tests of the parts included in the doctest directive
	echo.  coverage   to make a coverage check of the documentation
	goto end
)

if "%1" == "clean" (
	for /d %%i in (%BUILDDIR%\*) do rmdir /q /s %%i
	del /q /s %BUILDDIR%\*
	goto end
)


%SPHINXBUILD% -M %1 %ALLSPHINXOPTS% %O%
goto end

:end
popd
