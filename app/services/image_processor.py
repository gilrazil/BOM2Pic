import re
import io
import zipfile
import warnings
from io import BytesIO
from datetime import datetime
from typing import List, Tuple, Set, Dict, Any
from pathlib import Path

from ..utils.excel_image_extractor import extract_images_details
from ..config.settings import settings


class ImageProcessor:
    """Handles Excel image processing and ZIP generation."""
    
    def __init__(self):
        self.total_images = 0
        self.saved_count = 0
        self.duplicate_count = 0
        self.seen_names: Set[str] = set()
        self.manifest_rows: List[Tuple[str, str, int, str, str, str]] = []
    
    @staticmethod
    def detect_extension(image_bytes: bytes) -> str:
        """Detect image extension from bytes."""
        try:
            from PIL import Image
            with Image.open(BytesIO(image_bytes)) as im:
                fmt = (im.format or "PNG").lower()
        except Exception:
            fmt = "png"
        
        mapping = {
            "jpeg": "jpg",
            "jpg": "jpg",
            "png": "png",
            "webp": "webp",
            "gif": "gif",
            "tiff": "tif",
            "bmp": "bmp",
        }
        return mapping.get(fmt, "png")
    
    @staticmethod
    def normalize(name: str) -> str:
        """Normalize filename for safe storage."""
        n = (name or "").strip()
        n = n.replace(" ", "_")
        n = re.sub(r"[\\/:*?\"<>|]+", "", n)
        n = re.sub(r"_+", "_", n)
        n = n.lower()
        return n[:80] or "image"
    
    @staticmethod
    def safe_folder_name(name: str) -> str:
        """Create safe folder name from filename."""
        stem = Path(name).stem
        stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-")
        return stem or "workbook"
    
    def process_excel_file(self, contents: bytes, original_name: str, 
                          image_column: str, name_column: str) -> List[Dict[str, Any]]:
        """Process a single Excel file and return image details."""
        max_images = settings.MAX_IMAGES if settings.MAX_IMAGES > 0 else None
        
        details = extract_images_details(
            xlsx_bytes=contents,
            image_col_letter=image_column,
            name_col_letter=name_column,
            max_images=max_images,
        )
        
        if not details:
            return []
        
        processed_items = []
        for item in details:
            part_name_raw = item.name_raw
            base = self.normalize(part_name_raw)
            ext = self.detect_extension(item.image_bytes)
            final_name = f"{base}.{ext}"
            
            if final_name in self.seen_names:
                action = "Duplicate"
                self.duplicate_count += 1
            else:
                action = "Saved"
                self.saved_count += 1
                self.seen_names.add(final_name)
            
            processed_items.append({
                'final_name': final_name,
                'image_bytes': item.image_bytes,
                'manifest_row': (original_name, item.sheet, item.row, part_name_raw, final_name, action)
            })
            self.total_images += 1
        
        return processed_items
    
    def create_zip(self, processed_files: List[List[Dict[str, Any]]]) -> BytesIO:
        """Create ZIP file with all processed images."""
        # Suppress zipfile warnings
        warnings.filterwarnings("ignore", category=UserWarning, module="zipfile", message=r"Duplicate name: .*")
        
        zip_buffer = BytesIO()
        
        with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=7) as zf:
            images_dir = "images/"
            
            # Write all images
            for file_items in processed_files:
                for item in file_items:
                    zf.writestr(f"{images_dir}{item['final_name']}", item['image_bytes'])
                    self.manifest_rows.append(item['manifest_row'])
        
        # Add report.csv
        self._add_report_to_zip(zip_buffer)
        
        zip_buffer.seek(0)
        return zip_buffer
    
    def _add_report_to_zip(self, zip_buffer: BytesIO):
        """Add report.csv to the ZIP file."""
        with zipfile.ZipFile(zip_buffer, mode="a", compression=zipfile.ZIP_DEFLATED, compresslevel=7) as zf:
            import csv as _csv
            output = io.StringIO()
            writer = _csv.writer(output, lineterminator="\n")
            writer.writerow(["source_file", "sheet", "row", "part_name", "final_filename", "action"])
            
            for row in self.manifest_rows:
                writer.writerow(row)
            
            zf.writestr("report.csv", output.getvalue())
    
    def get_response_headers(self) -> Dict[str, str]:
        """Generate response headers for the ZIP download."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        
        return {
            "Content-Disposition": f"attachment; filename=bom2pic_{timestamp}.zip",
            "X-Content-Type-Options": "nosniff",
            "X-B2P-Processed": str(self.total_images),
            "X-B2P-Saved": str(self.saved_count),
            "X-B2P-Duplicate": str(self.duplicate_count),
        }
