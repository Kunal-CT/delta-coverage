diff-cover |pypi-version| |conda-version| |build-status|
========================================================================================

Automatically find diff lines that need test coverage.
Also finds diff lines that have violations (according to tools such
as pycodestyle, pyflakes, flake8, or pylint).
This is used as a code quality metric during code reviews.

Overview
--------

Diff coverage is the percentage of new or modified
lines that are covered by tests.  This provides a clear
and achievable standard for code review: If you touch a line
of code, that line should be covered.  Code coverage
is *every* developer's responsibility!

The ``diff-cover`` command line tool compares an XML coverage report
with the output of ``git diff``.  It then reports coverage information
for lines in the diff.

Currently, ``diff-cover`` requires that:

- You are using ``git`` for version control.
- Your test runner generates coverage reports in Cobertura, Clover
  or JaCoCo XML format, or LCov format.

Supported XML or LCov coverage reports can be generated with many coverage tools,
including:

- Cobertura__ (Java)
- Clover__ (Java)
- JaCoCo__ (Java)
- coverage.py__ (Python)
- JSCover__ (JavaScript)
- lcov__ (C/C++)

__ http://cobertura.sourceforge.net/
__ http://openclover.org/
__ https://www.jacoco.org/
__ http://nedbatchelder.com/code/coverage/
__ http://tntim96.github.io/JSCover/
__ https://ltp.sourceforge.net/coverage/lcov.php


``diff-cover`` is designed to be extended.  If you are interested
in adding support for other version control systems or coverage
report formats, see below for information on how to contribute!


Installation
------------

To install the latest release:

    pip install diff_cover


To install the development version:

    git clone https://github.com/Bachmann1234/diff-cover.git
    cd diff-cover
    poetry install
    poetry shell


Getting Started
---------------

1. Set the current working directory to a ``git`` repository.
2. Create your jacoco aggregate coverage report and run it using 

```
python3 <path>/diff_cover.py <aggregate_report_path>/jacoco.xml --compare-branch=origin/master --show-uncovered

