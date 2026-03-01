#!/usr/bin/env python
"""
Example: Automatic Semantic Versioning Workflow

This script demonstrates how the semantic versioning system works
with realistic gleplot development scenarios.
"""

import subprocess
from pathlib import Path

def run_example(title: str, description: str, commands: list):
    """Run an example workflow."""
    print(f"\n{'='*70}")
    print(f"EXAMPLE: {title}")
    print(f"{'='*70}")
    print(f"\n{description}\n")
    
    for cmd_type, cmd_display, cmd_execute in commands:
        if cmd_type == 'comment':
            print(f"  {cmd_display}")
        elif cmd_type == 'cmd':
            print(f"$ {cmd_display}")
        elif cmd_type == 'output':
            print(f"  {cmd_display}")
        elif cmd_type == 'exec':
            print(f"$ {cmd_display}")
            # Only show output for git commands
            if 'git' in cmd_execute:
                try:
                    result = subprocess.run(
                        cmd_execute,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.stdout:
                        for line in result.stdout.strip().split('\n'):
                            print(f"  {line}")
                except Exception as e:
                    print(f"  [Command execution skipped in example]")


def main():
    """Run workflow examples."""
    print("\nSEMANTIC VERSIONING WORKFLOW EXAMPLES")
    print("="*70)
    
    # Example 1: Bug fix release
    run_example(
        "Bug Fix Release (Patch Bump)",
        "You discovered and fixed a bug in the writer module.",
        [
            ('comment', "# Create a test file to demonstrate"),
            ('cmd', "cat > test_fix.py << 'EOF'"),
            ('output', "def buggy_function():\n    return 1 / 0  # Oops!\nEOF"),
            ('cmd', "git add test_fix.py"),
            ('cmd', "# Commit with fix: prefix to trigger PATCH bump"),
            ('exec', "git log --oneline -1"),
            ('cmd', "git commit -m 'fix: correct division by zero in writer module'"),
            ('cmd', "python scripts/bump_version.py --dry-run"),
            ('output', "\ngleplot Semantic Versioning\nVersion bump: PATCH\nCurrent: 0.0.1 → 0.0.2"),
            ('cmd', "# Actually bump version"),
            ('cmd', "python scripts/bump_version.py"),
            ('output', "\n✓ Version updated to 0.0.2\n✓ Tag created: v0.0.2"),
            ('cmd', "# Push to remote"),
            ('cmd', "git push origin main --follow-tags"),
        ]
    )
    
    # Example 2: New feature release
    run_example(
        "New Feature Release (Minor Bump)",
        "You added a new marker configuration system to gleplot.",
        [
            ('comment', "# Changes made to codebase..."),
            ('cmd', "git commit -m 'feat(markers): add configurable marker shapes'"),
            ('cmd', "git commit -m 'feat(markers): support custom marker sizes'"),
            ('cmd', "git commit -m 'docs: update with new marker examples'"),
            ('cmd', "python scripts/bump_version.py --dry-run"),
            ('output', "\nFound 2 commits\nVersion bump: MINOR\nCurrent: 0.0.1 → 0.1.0"),
            ('cmd', "python scripts/bump_version.py"),
            ('output', "\n✓ Version updated to 0.1.0\n✓ Tag created: v0.1.0"),
        ]
    )
    
    # Example 3: Breaking change
    run_example(
        "Breaking Change Release (Major Bump)",
        "You redesigned the API for creating figures (breaking change).",
        [
            ('cmd', "# Option 1: Using ! suffix"),
            ('cmd', "git commit -m 'feat!: redesign figure initialization API'"),
            ('cmd', "python scripts/bump_version.py --dry-run"),
            ('output', "\nFound 1 commits\nVersion bump: MAJOR\nCurrent: 0.0.1 → 1.0.0"),
            ('cmd', "# Option 2: Using BREAKING CHANGE footer"),
            ('cmd', "git commit -m 'refactor: simplify configuration system"),
            ('output', "BREAKING CHANGE: old API removed'"),
            ('cmd', "python scripts/bump_version.py --dry-run"),
            ('output', "\nVersion bump: MAJOR\nCurrent: 0.0.1 → 1.0.0"),
        ]
    )
    
    # Example 4: Multiple changes
    run_example(
        "Mixed Release (Auto-Detection)",
        "You've made multiple types of changes - system picks the highest level.",
        [
            ('cmd', "git commit -m 'fix: correct color conversion'"),
            ('cmd', "git commit -m 'feat: add color palette system'"),
            ('cmd', "git commit -m 'docs: update color guide'"),
            ('cmd', "python scripts/bump_version.py --dry-run"),
            ('output', "\nFound 3 commits\nVersion bump: MINOR (feat: is higher than fix:)"),
            ('output', "Current: 0.0.1 → 0.1.0"),
        ]
    )
    
    # Example 5: No changes
    run_example(
        "Documentation-Only Release",
        "You only updated documentation, tests, or code style.",
        [
            ('cmd', "git commit -m 'docs: major update to README'"),
            ('cmd', "git commit -m 'test: improve test coverage'"),
            ('cmd', "git commit -m 'style: apply code formatting'"),
            ('cmd', "python scripts/bump_version.py --dry-run"),
            ('output', "\nFound 3 commits\nNo version bump needed (docs, test, style ignored)"),
        ]
    )
    
    # Example 6: Using GitHub Actions
    run_example(
        "Automated Release via GitHub Actions",
        "Push to main and the workflow automatically bumps version.",
        [
            ('comment', "# Push commits with proper semantic commit messages"),
            ('cmd', "git commit -m 'feat: implement new plotting engine'"),
            ('cmd', "git push origin main"),
            ('output', "\nGitHub Actions workflow triggers automatically..."),
            ('output', "1. Analyzes commits since last tag"),
            ('output', "2. Detects MINOR version bump needed"),
            ('output', "3. Updates pyproject.toml and __init__.py"),
            ('output', "4. Creates commit and tag"),
            ('output', "5. Pushes everything back to main"),
            ('output', "\nResult: Version automatically bumped from 0.0.1 → 0.1.0"),
            ('output', "        Tag v0.1.0 created and pushed"),
        ]
    )
    
    # Example 7: Manual override
    run_example(
        "Manual Version Control",
        "Override automatic detection when needed.",
        [
            ('comment', "# Force specific version bump despite commit messages"),
            ('cmd', "python scripts/bump_version.py --major"),
            ('output', "\nForcing MAJOR version bump\nCurrent: 0.0.1 → 1.0.0"),
            ('cmd', "python scripts/bump_version.py --minor"),
            ('output', "\nForcing MINOR version bump\nCurrent: 0.0.1 → 0.1.0"),
            ('cmd', "python scripts/bump_version.py --patch"),
            ('output', "\nForcing PATCH version bump\nCurrent: 0.0.1 → 0.0.2"),
        ]
    )
    
    print(f"\n{'='*70}")
    print("WORKFLOW SUMMARY")
    print(f"{'='*70}")
    print("""
The semantic versioning system makes releases automatic and consistent:

1. WRITE CODE with proper commit messages:
   - fix: ... → bumps PATCH version
   - feat: ... → bumps MINOR version  
   - feat!: ... → bumps MAJOR version

2. PUSH CODE to main branch

3. AUTOMATIC or MANUAL versioning:
   - GitHub Actions detects the commits
   - Version bumps automatically
   - Tags are created
   - You can also run: python scripts/bump_version.py

4. PULL THE TAGS:
   git pull origin main --tags

That's it! The system handles the rest.

Benefits:
   ✓ Consistent versioning based on actual changes
   ✓ Automatic tag creation for releases
   ✓ Clear commit history that drives versioning
   ✓ Can be fully automated or manually controlled
   ✓ Integrates with package distribution
    """)


if __name__ == '__main__':
    main()
