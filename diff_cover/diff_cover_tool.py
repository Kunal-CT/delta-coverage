import argparse
import io
import logging
import os
import json
import sys
import warnings
import xml.etree.ElementTree as etree
from lxml import etree
import xml.dom.minidom

from diff_cover import DESCRIPTION, VERSION
from diff_cover.config_parser import Tool, get_config
from diff_cover.diff_reporter import GitDiffReporter
from diff_cover.git_diff import GitDiffFileTool, GitDiffTool
from diff_cover.git_path import GitPathTool
from diff_cover.report_generator import (
    GitHubAnnotationsReportGenerator,
    HtmlReportGenerator,
    JsonReportGenerator,
    MarkdownReportGenerator,
    StringReportGenerator,
)
from diff_cover.util import open_file
from diff_cover.violationsreporters.violations_reporter import (
    LcovCoverageReporter,
    XmlCoverageReporter,
)

FORMAT_HELP = "Format to use"
HTML_REPORT_DEFAULT_PATH = "diff-cover.html"
JSON_REPORT_DEFAULT_PATH = "diff-cover.json"
MARKDOWN_REPORT_DEFAULT_PATH = "diff-cover.md"
COMPARE_BRANCH_HELP = "Branch to compare"
CSS_FILE_HELP = "Write CSS into an external file"
FAIL_UNDER_HELP = (
    "Returns an error code if coverage or quality score is below this value"
)
IGNORE_STAGED_HELP = "Ignores staged changes"
IGNORE_UNSTAGED_HELP = "Ignores unstaged changes"
IGNORE_WHITESPACE = "When getting a diff ignore any and all whitespace"
EXCLUDE_HELP = "Exclude files, more patterns supported"
INCLUDE_HELP = "Files to include (glob pattern)"
SRC_ROOTS_HELP = "List of source directories (only for jacoco coverage reports)"
COVERAGE_FILE_HELP = "coverage report (XML or lcov.info)"
DIFF_RANGE_NOTATION_HELP = (
    "Git diff range notation to use when comparing branches, defaults to '...'"
)
QUIET_HELP = "Only print errors and failures"
SHOW_UNCOVERED = "Show uncovered lines on the console"
EXPAND_COVERAGE_REPORT = (
    "Append missing lines in coverage reports based on the hits of the previous line."
)
INCLUDE_UNTRACKED_HELP = "Include untracked files"
CONFIG_FILE_HELP = "The configuration file to use"
DIFF_FILE_HELP = "The diff file to use"
LOGGER = logging.getLogger(__name__)


def auto_detect_src_roots(xml_roots):
    """
    Auto-detect source roots based on the package structure in JaCoCo XML reports.
    
    Args:
        xml_roots: List of parsed XML documents (ElementTree objects)
        
    Returns:
        List of detected source root directories
    """
    # Extract package names from the reports
    packages = set()
    for xml_root in xml_roots:
        for pkg in xml_root.findall(".//package"):
            packages.add(pkg.get("name"))
    
    if not packages:
        LOGGER.warning("No packages found in JaCoCo reports, using default source roots")
        return ["src/main/java", "src/test/java"]
    
    # Common Java project source directories to check first
    common_src_dirs = [
        "src/main/java",
        "java/src/main/java",
        "src/test/java",
        "java/src/test/java",
        "java/core/src/main/java",
        "java/core/src/test/java",
    ]
    
    # Check if any common directories match our package structure
    detected_roots = []
    for src_dir in common_src_dirs:
        if os.path.exists(src_dir):
            for pkg in packages:
                pkg_path = os.path.join(src_dir, pkg.replace('/', os.sep))
                if os.path.exists(pkg_path):
                    if src_dir not in detected_roots:
                        detected_roots.append(src_dir)
                        LOGGER.info(f"Detected source root: {src_dir}")
                    break
    
    # If we didn't find any matches in common directories, search the entire project
    if not detected_roots:
        LOGGER.info("Searching for source roots in project directory...")
        for root, dirs, files in os.walk('.', topdown=True):
            # Skip hidden directories and common non-source directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in
                      ['target', 'build', 'node_modules', 'dist', '.git']]
            
            # Check if this directory contains any of our packages
            for pkg in packages:
                pkg_path = os.path.join(root, pkg.replace('/', os.sep))
                if os.path.exists(pkg_path):
                    if root not in detected_roots:
                        detected_roots.append(root)
                        LOGGER.info(f"Detected source root: {root}")
                    break
    
    # If we still didn't find anything, fall back to defaults
    if not detected_roots:
        LOGGER.warning("Could not detect source roots, using defaults")
        return ["src/main/java", "src/test/java"]
    
    return detected_roots



def format_type(value):
    """
    Accepts:
        --format html:path/to/file.html,json:path/to/file.json

        return: dict of strings to paths
    """
    return dict((item.split(":", 1) for item in value.split(",")) if value else {})


def parse_coverage_args(argv):
    """
    Parse command line arguments, returning a dict of
    valid options:

        {
            'coverage_file': COVERAGE_FILE,
            'html_report': None | HTML_REPORT,
            'json_report': None | JSON_REPORT,
            'external_css_file': None | CSS_FILE,
        }

    where `COVERAGE_FILE`, `HTML_REPORT`, `JSON_REPORT`, and `CSS_FILE` are paths.

    The path strings may or may not exist.
    """
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    print("Line 85 in diff_cover_tool.py",parser)
    parser.add_argument("coverage_files", type=str, help=COVERAGE_FILE_HELP, nargs="+")
    print("Line 87 in diff_cover_tool.py",parser)
    parser.add_argument(
        "--format",
        type=format_type,
        default="",
        help=FORMAT_HELP,
    )

    parser.add_argument(
        "--show-uncovered", action="store_true", default=None, help=SHOW_UNCOVERED
    )

    parser.add_argument(
        "--expand-coverage-report",
        action="store_true",
        default=None,
        help=EXPAND_COVERAGE_REPORT,
    )

    parser.add_argument(
        "--external-css-file",
        metavar="FILENAME",
        type=str,
        help=CSS_FILE_HELP,
    )

    parser.add_argument(
        "--compare-branch",
        metavar="BRANCH",
        type=str,
        help=COMPARE_BRANCH_HELP,
    )

    parser.add_argument(
        "--fail-under", metavar="SCORE", type=float, default=None, help=FAIL_UNDER_HELP
    )

    parser.add_argument(
        "--ignore-staged", action="store_true", default=None, help=IGNORE_STAGED_HELP
    )

    parser.add_argument(
        "--ignore-unstaged",
        action="store_true",
        default=None,
        help=IGNORE_UNSTAGED_HELP,
    )

    parser.add_argument(
        "--include-untracked",
        action="store_true",
        default=None,
        help=INCLUDE_UNTRACKED_HELP,
    )

    parser.add_argument(
        "--exclude", metavar="EXCLUDE", type=str, nargs="+", help=EXCLUDE_HELP
    )

    parser.add_argument(
        "--include", metavar="INCLUDE", type=str, nargs="+", help=INCLUDE_HELP
    )

    parser.add_argument(
        "--src-roots",
        metavar="DIRECTORY",
        type=str,
        nargs="+",
        help=SRC_ROOTS_HELP,
    )

    parser.add_argument(
        "--diff-range-notation",
        metavar="RANGE_NOTATION",
        type=str,
        choices=["...", ".."],
        help=DIFF_RANGE_NOTATION_HELP,
    )

    parser.add_argument("--version", action="version", version=f"diff-cover {VERSION}")

    parser.add_argument(
        "--ignore-whitespace",
        action="store_true",
        default=None,
        help=IGNORE_WHITESPACE,
    )

    parser.add_argument(
        "-q", "--quiet", action="store_true", default=None, help=QUIET_HELP
    )

    parser.add_argument(
        "-c", "--config-file", help=CONFIG_FILE_HELP, metavar="CONFIG_FILE"
    )

    parser.add_argument("--diff-file", type=str, default=None, help=DIFF_FILE_HELP)

    defaults = {
        "show_uncovered": False,
        "compare_branch": "origin/main",
        "fail_under": 0,
        "ignore_staged": False,
        "ignore_unstaged": False,
        "ignore_untracked": False,
        "src_roots": None,  # Will be auto-detected if not provided
        "ignore_whitespace": False,
        "diff_range_notation": "...",
        "quiet": False,
        "expand_coverage_report": False,
    }

    return get_config(parser=parser, argv=argv, defaults=defaults, tool=Tool.DIFF_COVER)


def generate_coverage_report(
    coverage_files,
    compare_branch,
    diff_tool,
    report_formats=None,
    css_file=None,
    ignore_staged=False,
    ignore_unstaged=False,
    include_untracked=False,
    exclude=None,
    include=None,
    src_roots=None,
    quiet=False,
    show_uncovered=False,
    expand_coverage_report=False,
):
    """
    Generate the diff coverage report, using kwargs from `parse_args()`.
    """
    diff = GitDiffReporter(
        compare_branch,
        git_diff=diff_tool,
        ignore_staged=ignore_staged,
        ignore_unstaged=ignore_unstaged,
        include_untracked=include_untracked,
        exclude=exclude,
        include=include,
    )
    print("Line 230 in diff_cover_tool.py",json.dumps(diff.__dict__, indent=2, default=str))
    print("line 232 in diff_cover_tool.py",coverage_files)
    print("\n========== DEBUG: Git Diff Summary ==========")
    changed_files = diff.src_paths_changed()
    print(f"Changed files ({len(changed_files)}): {changed_files}")

    for file in changed_files:
        changed_lines = diff.lines_changed(file)
        print(f"File: {file}")
        print(f"  Changed lines: {changed_lines}")
    print("=============================================\n")

    xml_roots = [
        etree.parse(coverage_file)
        for coverage_file in coverage_files
        if coverage_file.endswith(".xml")
    ]
    # xml_roots = []
    output_dir = "parsed_coverage_xml"  # Directory to store pretty XML files
    os.makedirs(output_dir, exist_ok=True)
    print("Line 233 - Parsing XML coverage files...")
    for coverage_file in coverage_files:
        if coverage_file.endswith(".xml"):
            print(f"DEBUG: Parsing XML file: {coverage_file}")
            try:
                tree = etree.parse(coverage_file)
                root = tree.getroot()
                xml_str = etree.tostring(root, encoding='unicode')
                pretty_xml = xml.dom.minidom.parseString(xml_str).toprettyxml(indent="  ")

                output_path = os.path.join(output_dir, f"pretty_{os.path.basename(coverage_file)}")
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(pretty_xml)
                print(f"✅ Pretty-printed XML written to: {output_path}")

            except Exception as e:
                print(f"❌ Error parsing XML from {coverage_file}: {e}")

    lcov_roots = [
        LcovCoverageReporter.parse(coverage_file)
        for coverage_file in coverage_files
        if not coverage_file.endswith(".xml")
    ]
    if xml_roots and lcov_roots:
        raise ValueError("Mixing LCov and XML reports is not supported yet")
    if xml_roots:
        # Auto-detect source roots if not provided
        if src_roots is None:
            src_roots = auto_detect_src_roots(xml_roots)
            print(f"Auto-detected source roots: {src_roots}")
        coverage = XmlCoverageReporter(xml_roots, src_roots, expand_coverage_report)
    else:
        # For LCOV reports, use default source roots if not provided
        if src_roots is None:
            src_roots = ["src/main/java", "src/test/java"]
        coverage = LcovCoverageReporter(lcov_roots, src_roots)
    print("Line 245 in diff_cover_tool.py",json.dumps(coverage.__dict__, indent=2, default=str))
    # Build a report generator
    if "html" in report_formats:
        html_report = report_formats["html"] or HTML_REPORT_DEFAULT_PATH
        css_url = css_file
        if css_url is not None:
            css_url = os.path.relpath(css_file, os.path.dirname(html_report))
        reporter = HtmlReportGenerator(coverage, diff, css_url=css_url)
        print("Line 285 in diff_cover_tool",reporter)
        with open_file(html_report, "wb") as output_file:
            reporter.generate_report(output_file)
        if css_file is not None:
            with open(css_file, "wb") as output_file:
                reporter.generate_css(output_file)

    if "json" in report_formats:
        json_report = report_formats["json"] or JSON_REPORT_DEFAULT_PATH
        reporter = JsonReportGenerator(coverage, diff)
        with open_file(json_report, "wb") as output_file:
            reporter.generate_report(output_file)

    if "markdown" in report_formats:
        markdown_report = report_formats["markdown"] or MARKDOWN_REPORT_DEFAULT_PATH
        reporter = MarkdownReportGenerator(coverage, diff)
        with open_file(markdown_report, "wb") as output_file:
            reporter.generate_report(output_file)

    if "github-annotations" in report_formats:
        # Github annotations are always written to stdout, but we can use different types
        reporter = GitHubAnnotationsReportGenerator(
            coverage,
            diff,
            report_formats["github-annotations"],
        )
        reporter.generate_report(sys.stdout.buffer)

    # Generate the report for stdout
    reporter = StringReportGenerator(coverage, diff, show_uncovered)
    print("At line 315 in diff_cover_tool ",reporter)
    print("Line 316 in diff_cover_tool",reporter.total_percent_covered())
    output_file = io.BytesIO() if quiet else sys.stdout.buffer

    # Generate the report
    reporter.generate_report(output_file)
    return reporter.total_percent_covered()


def handle_old_format(description, argv):
    parser = argparse.ArgumentParser(description=description)
    arg_html = parser.add_argument("--html-report", type=str)
    arg_json = parser.add_argument("--json-report", type=str)
    arg_markdown = parser.add_argument("--markdown-report", type=str)
    parser.add_argument("--format", type=str)

    known_args, unknown_args = parser.parse_known_args(argv)
    format_ = format_type(known_args.format)
    if known_args.html_report:
        if "html" in format_:
            raise argparse.ArgumentError(
                arg_html, "Cannot use along with --format html."
            )
        warnings.warn(
            "The --html-report option is deprecated. "
            f"Use --format html:{known_args.html_report} instead."
        )
        format_["html"] = known_args.html_report
    if known_args.json_report:
        if "json" in format_:
            raise argparse.ArgumentError(
                arg_json, "Cannot use along with --format json."
            )
        warnings.warn(
            "The --json-report option is deprecated. "
            f"Use --format json:{known_args.json_report} instead."
        )
        format_["json"] = known_args.json_report
    if known_args.markdown_report:
        if "markdown" in format_:
            raise argparse.ArgumentError(
                arg_markdown, "Cannot use along with --format markdown."
            )
        warnings.warn(
            "The --markdown-report option is deprecated. "
            f"Use --format markdown:{known_args.markdown_report} instead."
        )
        format_["markdown"] = known_args.markdown_report
    if format_:
        unknown_args += [
            "--format",
            ",".join(f"{k}:{v}" for k, v in format_.items()),  # noqa: E231
        ]
    return unknown_args


def main(argv=None, directory=None):
    """
    Main entry point for the tool, script installed via pyproject.toml
    Returns a value that can be passed into exit() specifying
    the exit code.
    1 is an error
    0 is successful run
    """
    argv = argv or sys.argv
    arg_dict = parse_coverage_args(handle_old_format(DESCRIPTION, argv[1:]))
    quiet = arg_dict["quiet"]
    level = logging.ERROR if quiet else logging.WARNING
    logging.basicConfig(format="%(message)s", level=level)

    GitPathTool.set_cwd(directory)
    fail_under = arg_dict.get("fail_under")
    diff_tool = None

    if not arg_dict["diff_file"]:
        diff_tool = GitDiffTool(
            arg_dict["diff_range_notation"], arg_dict["ignore_whitespace"]
        )
    else:
        diff_tool = GitDiffFileTool(arg_dict["diff_file"])

    percent_covered = generate_coverage_report(
        arg_dict["coverage_files"],
        arg_dict["compare_branch"],
        diff_tool,
        report_formats=arg_dict["format"],
        css_file=arg_dict["external_css_file"],
        ignore_staged=arg_dict["ignore_staged"],
        ignore_unstaged=arg_dict["ignore_unstaged"],
        include_untracked=arg_dict["include_untracked"],
        exclude=arg_dict["exclude"],
        include=arg_dict["include"],
        src_roots=arg_dict["src_roots"],
        quiet=quiet,
        show_uncovered=arg_dict["show_uncovered"],
        expand_coverage_report=arg_dict["expand_coverage_report"],
    )

    if percent_covered >= fail_under:
        return 0
    LOGGER.error("Failure. Coverage is below %i%%.", fail_under)
    return 1


if __name__ == "__main__":
    print("here line 388 diff_cover_tool.py")
    sys.exit(main())
