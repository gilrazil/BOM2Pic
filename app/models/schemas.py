from pydantic import BaseModel, Field
from typing import List, Optional

class ProcessRequest(BaseModel):
    """Request model for image processing."""
    imageColumn: str = Field(..., min_length=1, max_length=2, description="Column letter containing images (e.g., 'A')")
    nameColumn: str = Field(..., min_length=1, max_length=2, description="Column letter containing names/IDs (e.g., 'C')")

class ProcessResponse(BaseModel):
    """Response model for successful processing."""
    processed: int = Field(..., description="Total number of images processed")
    saved: int = Field(..., description="Number of unique images saved")
    duplicates: int = Field(..., description="Number of duplicate images found")
    
class ErrorResponse(BaseModel):
    """Error response model."""
    detail: str = Field(..., description="Error message")

class HealthResponse(BaseModel):
    """Health check response model."""
    status: str = Field(..., description="Service status")

class ProcessingStats(BaseModel):
    """Statistics about the processing operation."""
    total_files: int
    total_images: int
    saved_images: int
    duplicate_images: int
    processing_time_seconds: float
