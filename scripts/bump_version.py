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
from typing import Tuple, Optional
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
    
    def _get_commits_since_last_tag(self) -> list:
        """Get commit messages since last tag.
        
        Returns
        -------
        list
            List of commit messages and bodies
        """
        try:
            # Get last tag
            result = subprocess.run(
                ['git', 'describe', '--tags', '--abbrev=0'],
                cwd=self.root,
                capture_output=True,
                text=True,
                check=False
            )
            last_tag = result.stdout.strip() if result.returncode == 0 else None
            
            if last_tag:
                # Get commits since tag
                cmd = ['git', 'log', f'{last_tag}..HEAD', '--format=%B%x00']
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
        
        if has_breaking:
            return 'major'
        elif has_feature:
            return 'minor'
        elif has_fix:
            return 'patch'
        else:
            return 'none'
    
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
