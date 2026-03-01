"""Image analysis utilities for validating generated graphics."""

from pathlib import Path
from typing import Dict, Tuple, Optional
import re


class PDFAnalyzer:
    """Analyzer for PDF files."""
    
    def __init__(self, pdf_path: Path):
        """
        Initialize PDF analyzer.
        
        Parameters
        ----------
        pdf_path : Path
            Path to PDF file
        """
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    def is_valid_pdf(self) -> bool:
        """Check if file is a valid PDF."""
        try:
            content = self.pdf_path.read_bytes()
            return content.startswith(b'%PDF')
        except Exception:
            return False
    
    def get_file_size(self) -> int:
        """Get PDF file size in bytes."""
        return self.pdf_path.stat().st_size
    
    def has_valid_structure(self) -> bool:
        """Check if PDF has valid structure (contains key elements)."""
        try:
            content = self.pdf_path.read_bytes()
            # Check for essential PDF elements
            has_header = content.startswith(b'%PDF')
            has_stream = b'stream' in content
            has_endstream = b'endstream' in content
            has_xref = b'xref' in content or b'startxref' in content
            
            return has_header and has_stream and has_endstream and has_xref
        except Exception:
            return False
    
    def get_page_count(self) -> Optional[int]:
        """Extract number of pages from PDF."""
        try:
            content = self.pdf_path.read_text(errors='ignore')
            # Look for /Pages ... /Count pattern
            match = re.search(r'/Pages\s+\d+\s+0\s+R.*?/Count\s+(\d+)', content, re.DOTALL)
            if match:
                return int(match.group(1))
            # Alternative pattern
            match = re.search(r'/Count\s+(\d+)', content)
            if match:
                return int(match.group(1))
        except Exception:
            pass
        return None


class EPSAnalyzer:
    """Analyzer for EPS (Encapsulated PostScript) files."""
    
    def __init__(self, eps_path: Path):
        """
        Initialize EPS analyzer.
        
        Parameters
        ----------
        eps_path : Path
            Path to EPS file
        """
        self.eps_path = Path(eps_path)
        if not self.eps_path.exists():
            raise FileNotFoundError(f"EPS file not found: {eps_path}")
    
    def is_valid_eps(self) -> bool:
        """Check if file is a valid EPS."""
        try:
            content = self.eps_path.read_text(errors='ignore')
            return '%!PS-Adobe' in content or '%!PS' in content
        except Exception:
            return False
    
    def get_file_size(self) -> int:
        """Get EPS file size in bytes."""
        return self.eps_path.stat().st_size
    
    def has_valid_structure(self) -> bool:
        """Check if EPS has valid structure (contains key elements)."""
        try:
            content = self.eps_path.read_text(errors='ignore')
            has_header = '%!PS-Adobe' in content or '%!PS' in content
            has_showpage = 'showpage' in content
            has_bounding_box = '%%BoundingBox' in content
            
            return has_header and has_showpage
        except Exception:
            return False
    
    def get_bounding_box(self) -> Optional[Tuple[float, float, float, float]]:
        """Extract bounding box from EPS file."""
        try:
            content = self.eps_path.read_text(errors='ignore')
            match = re.search(r'%%BoundingBox:\s+([\d.-]+)\s+([\d.-]+)\s+([\d.-]+)\s+([\d.-]+)', content)
            if match:
                return tuple(float(x) for x in match.groups())
        except Exception:
            pass
        return None


class PNGAnalyzer:
    """Analyzer for PNG image files."""
    
    def __init__(self, png_path: Path):
        """
        Initialize PNG analyzer.
        
        Parameters
        ----------
        png_path : Path
            Path to PNG file
        """
        self.png_path = Path(png_path)
        if not self.png_path.exists():
            raise FileNotFoundError(f"PNG file not found: {png_path}")
    
    PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'
    
    def is_valid_png(self) -> bool:
        """Check if file is a valid PNG."""
        try:
            content = self.png_path.read_bytes()
            return content.startswith(self.PNG_SIGNATURE)
        except Exception:
            return False
    
    def get_file_size(self) -> int:
        """Get PNG file size in bytes."""
        return self.png_path.stat().st_size
    
    def get_image_dimensions(self) -> Optional[Tuple[int, int]]:
        """Extract image width and height from PNG."""
        try:
            content = self.png_path.read_bytes()
            
            # Check signature
            if not content.startswith(self.PNG_SIGNATURE):
                return None
            
            # IHDR chunk is usually at position 8-32
            if len(content) < 32:
                return None
            
            # IHDR chunk: width (4 bytes), height (4 bytes)
            width = int.from_bytes(content[16:20], 'big')
            height = int.from_bytes(content[20:24], 'big')
            
            return (width, height)
        except Exception:
            return None
    
    def get_color_depth(self) -> Optional[int]:
        """Extract color depth (bits per sample) from PNG."""
        try:
            content = self.png_path.read_bytes()
            
            if not content.startswith(self.PNG_SIGNATURE):
                return None
            
            if len(content) < 32:
                return None
            
            # IHDR chunk: bit depth is at position 24
            bit_depth = content[24]
            return bit_depth
        except Exception:
            return None


def validate_graphics_file(file_path: Path) -> Dict[str, any]:
    """
    Validate a generated graphics file.
    
    Parameters
    ----------
    file_path : Path
        Path to graphics file (PDF, EPS, or PNG)
    
    Returns
    -------
    dict
        Validation results with keys like 'valid', 'format', 'size', etc.
    """
    file_path = Path(file_path)
    suffix = file_path.suffix.lower()
    
    result = {
        'path': str(file_path),
        'format': suffix[1:] if suffix else 'unknown',
        'exists': file_path.exists(),
        'valid': False,
    }
    
    if not file_path.exists():
        return result
    
    result['size_bytes'] = file_path.stat().st_size
    result['size_kb'] = result['size_bytes'] / 1024
    
    try:
        if suffix.lower() == '.pdf':
            analyzer = PDFAnalyzer(file_path)
            result['valid'] = analyzer.is_valid_pdf()
            result['has_valid_structure'] = analyzer.has_valid_structure()
            result['page_count'] = analyzer.get_page_count()
        
        elif suffix.lower() == '.eps':
            analyzer = EPSAnalyzer(file_path)
            result['valid'] = analyzer.is_valid_eps()
            result['has_valid_structure'] = analyzer.has_valid_structure()
            result['bounding_box'] = analyzer.get_bounding_box()
        
        elif suffix.lower() == '.png':
            analyzer = PNGAnalyzer(file_path)
            result['valid'] = analyzer.is_valid_png()
            result['dimensions'] = analyzer.get_image_dimensions()
            result['color_depth'] = analyzer.get_color_depth()
    
    except Exception as e:
        result['error'] = str(e)
    
    return result
