"""GLE compiler wrapper for gleplot."""

import subprocess
import sys
from pathlib import Path
from typing import Optional, Literal


class GLECompiler:
    """Wrapper for GLE command-line compiler."""
    
    def __init__(self, gle_path: Optional[str] = None):
        """
        Initialize GLE compiler.
        
        Parameters
        ----------
        gle_path : str, optional
            Path to GLE executable. If None, searches system PATH.
        """
        self.gle_path = gle_path or self._find_gle()
        
        if not self.gle_path:
            raise RuntimeError("GLE not found. Install GLE or provide gle_path.")
    
    @staticmethod
    def _find_gle() -> Optional[str]:
        """Find GLE executable in system PATH."""
        for path in ['/usr/local/bin/gle', '/opt/homebrew/bin/gle', '/usr/bin/gle']:
            if Path(path).exists():
                return path
        
        # Try 'which' command
        try:
            result = subprocess.run(['which', 'gle'], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        
        return None
    
    def compile(
        self,
        input_file: str,
        output_format: Literal['pdf', 'png', 'eps'] = 'pdf',
        dpi: int = 150,
        verbose: bool = False
    ) -> Path:
        """
        Compile GLE file to output format.
        
        Parameters
        ----------
        input_file : str
            Path to .gle input file
        output_format : {'pdf', 'png', 'eps'}
            Output format
        dpi : int
            DPI for raster formats (png)
        verbose : bool
            Print compiler output
            
        Returns
        -------
        Path
            Path to output file
            
        Raises
        ------
        RuntimeError
            If compilation fails
        """
        input_path = Path(input_file).resolve()
        
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_file}")
        
        # Determine output file
        output_path = input_path.with_suffix(f'.{output_format}')
        
        # Build command
        cmd = [self.gle_path, input_path]
        cmd.extend([f'-d {output_format.upper()}'])
        
        if output_format == 'png':
            cmd.extend([f'-r {dpi}'])
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if verbose or result.returncode != 0:
                if result.stdout:
                    print(result.stdout)
                if result.stderr:
                    print(result.stderr, file=sys.stderr)
            
            if result.returncode != 0:
                raise RuntimeError(
                    f"GLE compilation failed: {result.stderr}"
                )
            
            if not output_path.exists():
                raise RuntimeError(
                    f"Output file not created: {output_path}"
                )
            
            return output_path
            
        except subprocess.TimeoutExpired:
            raise RuntimeError("GLE compilation timed out")
    
    def info(self) -> dict:
        """Get GLE version and info."""
        try:
            result = subprocess.run(
                [self.gle_path, '-info'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return {'version': result.stdout.strip()}
        except Exception as e:
            return {'error': str(e)}
