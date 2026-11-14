#!/usr/bin/env python
"""
Example: Automatic Semantic Versioning Workflow

Illustrates how conventional commits on main flow through Tests and Release.
Commands are shown for learning; they are not executed unless noted.
"""

import subprocess


def run_example(title: str, description: str, commands: list):
    """Run an example workflow."""
    print(f"\n{'=' * 70}")
    print(f"EXAMPLE: {title}")
    print(f"{'=' * 70}")
    print(f"\n{description}\n")

    for cmd_type, cmd_display, *rest in commands:
        cmd_execute = rest[0] if rest else cmd_display
        if cmd_type == "comment":
            print(f"  {cmd_display}")
        elif cmd_type == "cmd":
            print(f"$ {cmd_display}")
        elif cmd_type == "output":
            print(f"  {cmd_display}")
        elif cmd_type == "exec":
            print(f"$ {cmd_display}")
            if "git" in cmd_execute:
                try:
                    result = subprocess.run(
                        cmd_execute,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=5,
                        check=False,
                    )
                    if result.stdout:
                        for line in result.stdout.strip().split("\n"):
                            print(f"  {line}")
                except Exception:
                    print("  [Command execution skipped in example]")


def main():
    """Run workflow examples."""
    print("\nSEMANTIC VERSIONING WORKFLOW EXAMPLES")
    print("=" * 70)

    run_example(
        "Bug Fix Release (Patch Bump)",
        "A fix: commit on main triggers a patch release after Tests pass.",
        [
            ("cmd", "git commit -m 'fix: correct division by zero in writer module'", ""),
            ("cmd", "git push origin main", ""),
            ("output", "Tests workflow runs → Release workflow runs on success", ""),
            ("cmd", "semantic-release version --noop", ""),
            ("output", "Locally: would bump PATCH if no release-worthy commits since tag", ""),
        ],
    )

    run_example(
        "New Feature Release (Minor Bump)",
        "feat: commits since the last tag produce a minor release.",
        [
            ("cmd", "git commit -m 'feat(markers): add configurable marker shapes'", ""),
            ("cmd", "git commit -m 'docs: update marker examples'", ""),
            ("cmd", "git push origin main", ""),
            ("output", "Release: MINOR bump, tag vX.Y.Z, GitHub Release + dist/*", ""),
        ],
    )

    run_example(
        "Breaking Change (Major Bump)",
        "Breaking API changes use feat! or a BREAKING CHANGE footer.",
        [
            ("cmd", "git commit -m 'feat!: redesign figure initialization API'", ""),
            ("output", "Release: MAJOR bump", ""),
        ],
    )

    run_example(
        "Documentation Only",
        "docs/test/style commits do not cut a release.",
        [
            ("cmd", "git commit -m 'docs: major README update'", ""),
            ("cmd", "git push origin main", ""),
            ("output", "Tests run; Release exits with no new version", ""),
        ],
    )

    run_example(
        "Automated Release via GitHub Actions",
        "Default path: merge to main, wait for Tests, then Release.",
        [
            ("output", "1. Push conventional commits to main", ""),
            ("output", "2. Tests matrix must pass", ""),
            ("output", "3. Release bumps, tags, updates CHANGELOG, uploads wheels to GitHub", ""),
            ("output", "4. PyPI job runs only when PYPI_PUBLISH=true", ""),
        ],
    )

    run_example(
        "Manual Override",
        "Maintainers can force a bump from the Actions UI.",
        [
            ("output", "Actions → Release → Run workflow", ""),
            ("output", "Choose major, minor, patch, or auto", ""),
        ],
    )

    print(f"\n{'=' * 70}")
    print("WORKFLOW SUMMARY")
    print(f"{'=' * 70}")
    print(
        """
1. WRITE CODE with conventional commits (feat / fix / perf / breaking).
2. PUSH to main and let Tests pass.
3. RELEASE workflow cuts GitHub Releases when warranted.
4. Preview locally: pip install -e ".[dev]" && semantic-release version --noop

See docs/guides/VERSIONING.md and .github/workflows/release.yml.
"""
    )


if __name__ == "__main__":
    main()