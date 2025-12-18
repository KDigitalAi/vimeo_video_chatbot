#!/usr/bin/env python3
"""
Auto-update Supabase with new PDFs (PDF-only mode)
Automatically detects new PDF content and generates embeddings without duplicates.
"""
import os
import sys
import time
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import logging

# Add project root to path
sys.path.append('.')

from app.config.settings import settings
from app.database.supabase import get_supabase
from app.services.pdf_ingestion import run_pdf_ingestion_from_path, generate_pdf_id_from_content

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('scripts/auto_update.log')
    ]
)
logger = logging.getLogger(__name__)

class AutoUpdateEmbeddings:
    """Auto-update embeddings for new PDFs (PDF-only mode)."""
    
    def __init__(self):
        """Initialize the auto-update system."""
        self.supabase = get_supabase()
        self.uploads_dir = Path("uploads/pdfs")
        # processed_videos removed - PDF-only mode
        self.processed_pdfs = set()
        
        # Ensure uploads directory exists
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("Auto-update embeddings system initialized")
    
    # Video-related methods removed - PDF-only mode
    
    def check_pdf_exists_in_supabase(self, pdf_id: str) -> bool:
        """
        Check if PDF already exists in Supabase.
        
        Args:
            pdf_id: PDF identifier
            
        Returns:
            True if PDF exists, False otherwise
        """
        try:
            result = self.supabase.table('pdf_embeddings').select('pdf_id').eq('pdf_id', pdf_id).limit(1).execute()
            return len(result.data) > 0
        except Exception as e:
            logger.error(f"Error checking PDF existence: {e}")
            return False
    
    
    def detect_new_pdfs_in_uploads(self) -> List[Path]:
        """
        Detect new PDF files in uploads directory.
        
        Returns:
            List of PDF file paths
        """
        try:
            pdf_files = []
            
            if not self.uploads_dir.exists():
                logger.warning(f"Uploads directory {self.uploads_dir} does not exist")
                return pdf_files
            
            for file_path in self.uploads_dir.glob("**/*.pdf"):
                if file_path.is_file():
                    pdf_files.append(file_path)
            
            logger.info(f"Found {len(pdf_files)} PDF files in uploads directory")
            return pdf_files
            
        except Exception as e:
            logger.error(f"Error detecting PDF files: {e}")
            return []
    
    
    
    # process_video method removed - PDF-only mode
    
    def process_pdf(self, pdf_path: Path) -> int:
        """
        Process a single PDF using the shared PDF ingestion service.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Number of embeddings inserted (chunk count)
        """
        logger.info(f"Processing PDF: {pdf_path.name}")
        
        # Use shared PDF ingestion service
        result = run_pdf_ingestion_from_path(
            pdf_path=str(pdf_path),
            pdf_id=None,  # Will be generated from content hash
            pdf_title=pdf_path.stem,
            force_reprocess=False
        )
        
        if result.success:
            logger.info(f"Successfully processed PDF {pdf_path.name}: {result.chunks_processed} chunks")
            self.processed_pdfs.add(result.pdf_id)
            return result.chunks_processed
        else:
            logger.warning(f"PDF processing failed for {pdf_path.name}: {result.error}")
            return 0
    
    # run_video_update method removed - PDF-only mode
    
    def run_pdf_update(self) -> Tuple[int, int]:
        """
        Process new PDFs from uploads directory.
        
        Returns:
            Tuple of (total_pdfs_processed, total_embeddings_inserted)
        """
        logger.info("=== PROCESSING PDF FILES ===")
        
        pdf_files = self.detect_new_pdfs_in_uploads()
        if not pdf_files:
            logger.info("No PDF files to process")
            return 0, 0
        
        total_processed = 0
        total_embeddings = 0
        
        for pdf_path in pdf_files:
            try:
                embeddings_count = self.process_pdf(pdf_path)
                if embeddings_count > 0:
                    total_processed += 1
                    total_embeddings += embeddings_count
            except Exception as e:
                logger.error(f"Error processing PDF {pdf_path}: {e}")
                continue
        
        logger.info(f"PDF processing complete: {total_processed} PDFs processed, {total_embeddings} embeddings inserted")
        return total_processed, total_embeddings
    
    def run(self) -> Dict[str, Any]:
        """
        Run the complete auto-update process (PDF-only mode).
        
        Returns:
            Summary of processing results
        """
        start_time = time.time()
        logger.info("Starting auto-update embeddings process (PDF-only mode)...")
        
        # Process PDFs only
        pdfs_processed, pdf_embeddings = self.run_pdf_update()
        
        # Calculate totals
        total_processed = pdfs_processed
        total_embeddings = pdf_embeddings
        processing_time = time.time() - start_time
        
        # Create summary
        summary = {
            'pdfs_processed': pdfs_processed,
            'pdf_embeddings_inserted': pdf_embeddings,
            'total_processed': total_processed,
            'total_embeddings_inserted': total_embeddings,
            'processing_time_seconds': round(processing_time, 2),
            'timestamp': datetime.now().isoformat()
        }
        
        logger.info("=== AUTO-UPDATE COMPLETE ===")
        logger.info(f"PDFs processed: {pdfs_processed}")
        logger.info(f"PDF embeddings inserted: {pdf_embeddings}")
        logger.info(f"Total processing time: {processing_time:.2f} seconds")
        
        return summary

def main():
    """Main entry point for the auto-update script."""
    try:
        # Initialize auto-update system
        auto_update = AutoUpdateEmbeddings()
        
        # Run the update process (PDF-only mode)
        summary = auto_update.run()
        
        # Print summary
        print("\n" + "="*60)
        print("AUTO-UPDATE EMBEDDINGS SUMMARY (PDF-ONLY MODE)")
        print("="*60)
        print(f"PDFs processed: {summary['pdfs_processed']}")
        print(f"PDF embeddings inserted: {summary['pdf_embeddings_inserted']}")
        print(f"Total processing time: {summary['processing_time_seconds']} seconds")
        print(f"Completed at: {summary['timestamp']}")
        print("="*60)
        
        return summary
        
    except Exception as e:
        logger.error(f"Fatal error in main: {e}")
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    main()
