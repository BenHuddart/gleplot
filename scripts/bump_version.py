#!/usr/bin/env python
"""
Automatic semantic versioning script for gleplot.

Follows conventional commits specification:
- feat: feature (minor bump)
- fix: fix (patch bump)
- BREAKING CHANGE: breaking change (major bump)

Usage:
    python scripts/bump_version.py [--dry-run] [--major|--minor|--patch]
"""

import re
import sys
import subprocess
from pathlib import Path
from typing import Tuple, Optional, List, Dict
import argparse


class SemanticVersioner:
    """Handle semantic versioning for gleplot."""
    
    def __init__(self, project_root: Path = None):
        """Initialize versioner.
        
        Parameters
        ----------
        project_root : Path, optional
            Root directory of project (default: current directory)
        """
        self.root = Path(project_root or '.')
        self.pyproject = self.root / 'pyproject.toml'
        self.init_file = self.root / 'src' / 'gleplot' / '__init__.py'
        self.current_version = self._read_current_version()
    
    def _read_current_version(self) -> Tuple[int, int, int]:
        """Read current version from pyproject.toml.
        
        Returns
        -------
        tuple
            (major, minor, patch) version numbers
        """
        with open(self.pyproject) as f:
            for line in f:
                if line.startswith('version = '):
                    version_str = line.split('"')[1]
                    parts = version_str.split('.')
                    return tuple(int(p) for p in parts[:3])
        raise ValueError("Could not find version in pyproject.toml")

    def _get_last_tag(self) -> Optional[str]:
        """Get most recent git tag, if any."""
        result = subprocess.run(
            ['git', 'describe', '--tags', '--abbrev=0'],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False
        )
        return result.stdout.strip() if result.returncode == 0 else None

    def _get_range_since_last_tag(self) -> Optional[str]:
        """Get git revision range from last tag to HEAD.

        Returns
        -------
        str or None
            Revision range string (e.g. v1.2.3..HEAD), or None if no tag exists.
        """
        last_tag = self._get_last_tag()
        if last_tag:
            return f'{last_tag}..HEAD'
        return None
    
    def _get_commits_since_last_tag(self) -> list:
        """Get commit messages since last tag.
        
        Returns
        -------
        list
            List of commit messages and bodies
        """
        try:
            range_spec = self._get_range_since_last_tag()

            if range_spec:
                # Get commits since tag
                cmd = ['git', 'log', range_spec, '--format=%B%x00']
            else:
                # Get all commits (first time)
                cmd = ['git', 'log', '--format=%B%x00']
            
            result = subprocess.run(
                cmd,
                cwd=self.root,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Split by null separator and clean
            commits = [c.strip() for c in result.stdout.split('\x00') if c.strip()]
            return commits
        
        except subprocess.CalledProcessError as e:
            print(f"Error getting commits: {e}", file=sys.stderr)
            return []

    def _get_changed_files_since_last_tag(self) -> List[Dict[str, str]]:
        """Get changed files since last tag.

        Returns
        -------
        list of dict
            Items with keys: status, path
        """
        try:
            range_spec = self._get_range_since_last_tag()
            if range_spec:
                cmd = ['git', 'diff', '--name-status', range_spec]
            else:
                cmd = ['git', 'log', '--name-status', '--pretty=format:', 'HEAD']

            result = subprocess.run(
                cmd,
                cwd=self.root,
                capture_output=True,
                text=True,
                check=True
            )

            changed_files: List[Dict[str, str]] = []
            for line in result.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue

                parts = line.split('\t', 1)
                if len(parts) != 2:
                    continue

                status, path = parts
                changed_files.append({'status': status, 'path': path})

            return changed_files
        except subprocess.CalledProcessError as e:
            print(f"Error getting changed files: {e}", file=sys.stderr)
            return []
    
    def _analyze_commits(self, commits: list) -> str:
        """Analyze commits and determine version bump.
        
        Parameters
        ----------
        commits : list
            List of commit messages
        
        Returns
        -------
        str
            'major', 'minor', 'patch', or 'none'
        """
        has_breaking = False
        has_feature = False
        has_fix = False
        has_perf = False
        
        for commit in commits:
            # Check for breaking change
            if 'BREAKING CHANGE:' in commit or re.search(r'^[a-z]+!:', commit, re.MULTILINE):
                has_breaking = True
            # Check for feature
            elif re.search(r'^feat(\(.+\))?!?:', commit, re.MULTILINE):
                has_feature = True
            # Check for fix
            elif re.search(r'^fix(\(.+\))?!?:', commit, re.MULTILINE):
                has_fix = True
            # Check for performance improvements
            elif re.search(r'^perf(\(.+\))?!?:', commit, re.MULTILINE):
                has_perf = True
        
        if has_breaking:
            return 'major'
        elif has_feature:
            return 'minor'
        elif has_fix or has_perf:
            return 'patch'
        else:
            return 'none'

    def _is_non_functional_change(self, path: str) -> bool:
        """Determine if file change is non-functional for release bumping."""
        non_functional_prefixes = (
            'docs/',
            'tests/',
            'examples/',
            '.github/',
            'test_graphics_output/',
            'test_custom_prefix_output/',
            '__pycache__/',
        )
        non_functional_suffixes = ('.md', '.rst', '.txt')

        if path.startswith(non_functional_prefixes):
            return True
        if path.endswith(non_functional_suffixes):
            return True
        if '__pycache__' in path:
            return True
        return False

    def _analyze_changed_files(self, changed_files: List[Dict[str, str]]) -> str:
        """Infer version bump from changed files when commit messages are inconclusive.

        Rules:
        - Added source module under src/gleplot/*.py -> minor
        - Modified/deleted source under src/gleplot/* -> patch
        - Packaging/runtime config changes (pyproject.toml, scripts/*.py) -> patch
        - Docs/tests/examples/output-only changes -> none
        - Any other non-trivial change -> patch (conservative default)
        """
        if not changed_files:
            return 'none'

        meaningful = [
            change for change in changed_files
            if not self._is_non_functional_change(change['path'])
        ]

        if not meaningful:
            return 'none'

        has_added_source_module = any(
            change['status'].startswith('A')
            and change['path'].startswith('src/gleplot/')
            and change['path'].endswith('.py')
            and change['path'] != 'src/gleplot/__init__.py'
            for change in meaningful
        )
        if has_added_source_module:
            return 'minor'

        has_source_change = any(
            change['path'].startswith('src/gleplot/')
            for change in meaningful
        )
        if has_source_change:
            return 'patch'

        has_packaging_or_runtime_change = any(
            change['path'] == 'pyproject.toml'
            or change['path'].startswith('scripts/')
            for change in meaningful
        )
        if has_packaging_or_runtime_change:
            return 'patch'

        return 'patch'
    
    def determine_version_bump(self) -> str:
        """Determine what version bump is needed.
        
        Returns
        -------
        str
            'major', 'minor', 'patch', or 'none'
        """
        commits = self._get_commits_since_last_tag()
        
        if not commits:
            print("No commits since last tag")
            return 'none'
        
        bump = self._analyze_commits(commits)
        if bump == 'none':
            changed_files = self._get_changed_files_since_last_tag()
            fallback_bump = self._analyze_changed_files(changed_files)
            if fallback_bump != 'none':
                bump = fallback_bump
                print("Commit messages did not request a bump; using file-change fallback")

        print(f"Found {len(commits)} commits")
        print(f"Version bump needed: {bump.upper()}")
        return bump
    
    def bump_version(self, bump_type: str) -> Tuple[int, int, int]:
        """Bump version according to semantic versioning.
        
        Parameters
        ----------
        bump_type : str
            'major', 'minor', or 'patch'
        
        Returns
        -------
        tuple
            New (major, minor, patch) version
        """
        major, minor, patch = self.current_version
        
        if bump_type == 'major':
            major += 1
            minor = 0
            patch = 0
        elif bump_type == 'minor':
            minor += 1
            patch = 0
        elif bump_type == 'patch':
            patch += 1
        elif bump_type == 'none':
            return (major, minor, patch)
        else:
            raise ValueError(f"Invalid bump type: {bump_type}")
        
        return (major, minor, patch)
    
    def format_version(self, version: Tuple[int, int, int]) -> str:
        """Format version tuple as string.
        
        Parameters
        ----------
        version : tuple
            (major, minor, patch)
        
        Returns
        -------
        str
            Formatted version string
        """
        return '.'.join(str(v) for v in version)
    
    def update_files(self, new_version: Tuple[int, int, int], dry_run: bool = False) -> None:
        """Update version in all project files.
        
        Parameters
        ----------
        new_version : tuple
            New (major, minor, patch) version
        dry_run : bool
            If True, don't actually write files
        """
        version_str = self.format_version(new_version)
        old_version_str = self.format_version(self.current_version)
        
        print(f"\nUpdating version: {old_version_str} → {version_str}")
        
        # Update pyproject.toml
        print(f"  Updating {self.pyproject}")
        with open(self.pyproject) as f:
            content = f.read()
        
        content = re.sub(
            r'version = "[\d.]+"',
            f'version = "{version_str}"',
            content
        )
        
        if not dry_run:
            with open(self.pyproject, 'w') as f:
                f.write(content)
        
        # Update __init__.py
        print(f"  Updating {self.init_file}")
        with open(self.init_file) as f:
            content = f.read()
        
        content = re.sub(
            r"__version__ = '[^']+'",
            f"__version__ = '{version_str}'",
            content
        )
        
        if not dry_run:
            with open(self.init_file, 'w') as f:
                f.write(content)
        
        print(f"✓ Version updated to {version_str}")
    
    def create_version_tag(self, version: Tuple[int, int, int], dry_run: bool = False) -> None:
        """Create git tag for version.
        
        Parameters
        ----------
        version : tuple
            (major, minor, patch) version
        dry_run : bool
            If True, don't actually create tag
        """
        tag = f"v{self.format_version(version)}"
        
        print(f"\nCreating git tag: {tag}")
        
        if not dry_run:
            try:
                # Stage changes
                subprocess.run(
                    ['git', 'add', str(self.pyproject), str(self.init_file)],
                    cwd=self.root,
                    check=True
                )
                
                # Commit version bump
                subprocess.run(
                    ['git', 'commit', '-m', f'chore: bump version to {self.format_version(version)}'],
                    cwd=self.root,
                    check=True
                )
                
                # Create tag
                subprocess.run(
                    ['git', 'tag', '-a', tag, '-m', f'Release {tag}'],
                    cwd=self.root,
                    check=True
                )
                
                print(f"✓ Tag created: {tag}")
                print(f"\nTo push changes:")
                print(f"  git push origin main")
                print(f"  git push origin {tag}")
            
            except subprocess.CalledProcessError as e:
                print(f"✗ Error creating tag: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            print(f"[DRY RUN] Would create tag: {tag}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Automatic semantic versioning for gleplot'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    parser.add_argument(
        '--major',
        action='store_true',
        help='Force major version bump'
    )
    parser.add_argument(
        '--minor',
        action='store_true',
        help='Force minor version bump'
    )
    parser.add_argument(
        '--patch',
        action='store_true',
        help='Force patch version bump'
    )
    
    args = parser.parse_args()
    
    # Determine project root
    project_root = Path(__file__).parent.parent
    
    # Create versioner
    versioner = SemanticVersioner(project_root)
    
    print(f"gleplot Semantic Versioning")
    print(f"===========================")
    print(f"Current version: {versioner.format_version(versioner.current_version)}")
    
    # Determine version bump
    if args.major:
        bump_type = 'major'
    elif args.minor:
        bump_type = 'minor'
    elif args.patch:
        bump_type = 'patch'
    else:
        bump_type = versioner.determine_version_bump()
    
    if bump_type == 'none':
        print("No version bump needed")
        sys.exit(0)
    
    # Calculate new version
    new_version = versioner.bump_version(bump_type)
    new_version_str = versioner.format_version(new_version)
    
    # Update files
    versioner.update_files(new_version, dry_run=args.dry_run)
    
    # Create tag
    versioner.create_version_tag(new_version, dry_run=args.dry_run)
    
    if args.dry_run:
        print("\n[DRY RUN] No changes were made")
    else:
        print(f"\n✓ Version bumped to {new_version_str}")


if __name__ == '__main__':
    main()
