#!/usr/bin/env python3
"""
Auto-update Supabase with new Vimeo videos & PDFs
Automatically detects new content and generates embeddings without duplicates.
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
from app.services.vimeo_loader import get_user_videos
from app.services.transcript_manager import get_transcript_segments_from_vimeo
from app.services.whisper_transcriber import transcribe_vimeo_audio
from app.services.pdf_processor import process_pdf_file
from app.services.text_processor import make_chunks_with_metadata
from app.services.vector_store_direct import store_embeddings_directly
from app.services.embedding_manager import get_embeddings_instance

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('auto_update.log')
    ]
)
logger = logging.getLogger(__name__)

class AutoUpdateEmbeddings:
    """Auto-update embeddings for new Vimeo videos and PDFs."""
    
    def __init__(self):
        """Initialize the auto-update system."""
        self.supabase = get_supabase()
        self.embeddings = get_embeddings_instance()
        self.uploads_dir = Path("uploads/pdfs")
        self.processed_videos = set()
        self.processed_pdfs = set()
        
        # Ensure uploads directory exists
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("Auto-update embeddings system initialized")
    
    def fetch_new_videos_from_vimeo(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Fetch new videos from Vimeo account.
        
        Args:
            limit: Maximum number of videos to fetch
            
        Returns:
            List of video metadata dictionaries
        """
        try:
            logger.info(f"Fetching up to {limit} videos from Vimeo...")
            videos = get_user_videos(limit=limit)
            
            if not videos:
                logger.warning("No videos found in Vimeo account")
                return []
            
            logger.info(f"Found {len(videos)} videos from Vimeo")
            return videos
            
        except Exception as e:
            logger.error(f"Error fetching videos from Vimeo: {e}")
            return []
    
    def extract_video_transcript(self, video_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        Extract transcript from a Vimeo video.
        First tries Vimeo captions, then falls back to Whisper transcription.
        
        Args:
            video_id: Vimeo video ID
            
        Returns:
            List of transcript segments or None if failed
        """
        try:
            logger.info(f"Extracting transcript for video {video_id}...")
            
            # First, try to get Vimeo captions
            segments = get_transcript_segments_from_vimeo(video_id)
            
            if segments and len(segments) > 0:
                logger.info(f"Successfully extracted {len(segments)} transcript segments from Vimeo captions")
                return segments
            else:
                # No Vimeo captions found, try Whisper transcription
                logger.info("No Vimeo captions found — generating transcript via Whisper...")
                
                try:
                    whisper_segments = transcribe_vimeo_audio(video_id)
                    
                    if whisper_segments and len(whisper_segments) > 0:
                        logger.info(f"Whisper transcript generated with {len(whisper_segments)} segments")
                        return whisper_segments
                    else:
                        logger.warning(f"Whisper transcription failed for video {video_id}")
                        return None
                        
                except Exception as whisper_error:
                    logger.error(f"Whisper transcription failed for video {video_id}: {whisper_error}")
                    return None
                
        except Exception as e:
            logger.error(f"Error extracting transcript for video {video_id}: {e}")
            return None
    
    def generate_embeddings(self, content: str) -> List[float]:
        """
        Generate embeddings for content using OpenAI.
        
        Args:
            content: Text content to embed
            
        Returns:
            List of embedding vectors
        """
        try:
            embedding = self.embeddings.embed_query(content)
            return embedding
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            return []
    
    def check_video_exists_in_supabase(self, video_id: str) -> bool:
        """
        Check if video already exists in Supabase.
        
        Args:
            video_id: Vimeo video ID
            
        Returns:
            True if video exists, False otherwise
        """
        try:
            result = self.supabase.table('video_embeddings').select('video_id').eq('video_id', video_id).limit(1).execute()
            return len(result.data) > 0
        except Exception as e:
            logger.error(f"Error checking video existence: {e}")
            return False
    
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
    
    def insert_video_embeddings_to_supabase(self, video_data: Dict[str, Any], chunks: List[Dict[str, Any]]) -> int:
        """
        Insert video embeddings into Supabase.
        
        Args:
            video_data: Video metadata
            chunks: Processed text chunks with metadata
            
        Returns:
            Number of embeddings inserted
        """
        try:
            # Extract video ID from URI (e.g., "/videos/1129411229" -> "1129411229")
            video_uri = video_data.get('uri', '')
            video_id = video_uri.split('/')[-1] if video_uri else str(video_data.get('id', 'unknown'))
            video_title = video_data.get('name', f'Video {video_id}')
            
            # Check if video already exists
            if self.check_video_exists_in_supabase(video_id):
                logger.info(f"Video {video_id} already exists in Supabase, skipping...")
                return 0
            
            # Store embeddings
            stored_count = store_embeddings_directly(chunks, table_name='video_embeddings')
            
            if stored_count > 0:
                logger.info(f"Successfully inserted {stored_count} embeddings for video {video_id}: {video_title}")
                self.processed_videos.add(video_id)
            else:
                logger.warning(f"No embeddings were stored for video {video_id}")
            
            return stored_count
            
        except Exception as e:
            logger.error(f"Error inserting video embeddings: {e}")
            return 0
    
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
            
            for file_path in self.uploads_dir.glob("*.pdf"):
                if file_path.is_file():
                    pdf_files.append(file_path)
            
            logger.info(f"Found {len(pdf_files)} PDF files in uploads directory")
            return pdf_files
            
        except Exception as e:
            logger.error(f"Error detecting PDF files: {e}")
            return []
    
    def extract_pdf_text(self, pdf_path: Path) -> Optional[List[Dict[str, Any]]]:
        """
        Extract text and create chunks from PDF file.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            List of processed chunks or None if failed
        """
        try:
            logger.info(f"Processing PDF: {pdf_path.name}")
            
            # Generate unique PDF ID based on file hash
            with open(pdf_path, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()[:12]
            
            pdf_id = f"pdf_{file_hash}"
            pdf_title = pdf_path.stem
            
            # Process PDF file
            chunks = process_pdf_file(str(pdf_path), pdf_id, pdf_title)
            
            if chunks:
                logger.info(f"Successfully processed {len(chunks)} chunks from PDF {pdf_path.name}")
                return chunks
            else:
                logger.warning(f"No chunks generated from PDF {pdf_path.name}")
                return None
                
        except Exception as e:
            logger.error(f"Error processing PDF {pdf_path}: {e}")
            return None
    
    def insert_pdf_embeddings_to_supabase(self, pdf_data: Dict[str, Any], chunks: List[Dict[str, Any]]) -> int:
        """
        Insert PDF embeddings into Supabase.
        
        Args:
            pdf_data: PDF metadata
            chunks: Processed text chunks with metadata
            
        Returns:
            Number of embeddings inserted
        """
        try:
            pdf_id = pdf_data['pdf_id']
            
            # Check if PDF already exists
            if self.check_pdf_exists_in_supabase(pdf_id):
                logger.info(f"PDF {pdf_id} already exists in Supabase, skipping...")
                return 0
            
            # Store embeddings
            stored_count = store_embeddings_directly(chunks, table_name='pdf_embeddings')
            
            if stored_count > 0:
                logger.info(f"Successfully inserted {stored_count} embeddings for PDF {pdf_id}")
                self.processed_pdfs.add(pdf_id)
            else:
                logger.warning(f"No embeddings were stored for PDF {pdf_id}")
            
            return stored_count
            
        except Exception as e:
            logger.error(f"Error inserting PDF embeddings: {e}")
            return 0
    
    def process_video(self, video_data: Dict[str, Any]) -> int:
        """
        Process a single video: extract transcript, create chunks, and store embeddings.
        
        Args:
            video_data: Video metadata from Vimeo
            
        Returns:
            Number of embeddings inserted
        """
        # Extract video ID from URI (e.g., "/videos/1129411229" -> "1129411229")
        video_uri = video_data.get('uri', '')
        video_id = video_uri.split('/')[-1] if video_uri else str(video_data.get('id', 'unknown'))
        video_title = video_data.get('name', f'Video {video_id}')
        
        logger.info(f"Processing video: {video_title} (ID: {video_id})")
        
        # Extract transcript (with Whisper fallback)
        segments = self.extract_video_transcript(video_id)
        if not segments:
            logger.warning(f"No transcript available for video {video_id}, skipping...")
            return 0
        
        # Verify transcript content is not empty
        total_text = " ".join([seg.get("text", "") for seg in segments if seg.get("text")])
        if not total_text.strip():
            logger.warning(f"Transcript is empty for video {video_id}, skipping...")
            return 0
        
        # Create chunks with metadata
        try:
            chunks = make_chunks_with_metadata(segments, video_id, video_title)
            if not chunks:
                logger.warning(f"No chunks created for video {video_id}")
                return 0
        except Exception as e:
            logger.error(f"Error creating chunks for video {video_id}: {e}")
            return 0
        
        # Insert embeddings
        embeddings_count = self.insert_video_embeddings_to_supabase(video_data, chunks)
        
        if embeddings_count > 0:
            logger.info(f"Transcript generated and embeddings inserted successfully ({embeddings_count} embeddings)")
        
        return embeddings_count
    
    def process_pdf(self, pdf_path: Path) -> int:
        """
        Process a single PDF: extract text, create chunks, and store embeddings.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Number of embeddings inserted
        """
        logger.info(f"Processing PDF: {pdf_path.name}")
        
        # Extract text and create chunks
        chunks = self.extract_pdf_text(pdf_path)
        if not chunks:
            return 0
        
        # Generate PDF metadata
        with open(pdf_path, 'rb') as f:
            file_hash = hashlib.md5(f.read()).hexdigest()[:12]
        
        pdf_data = {
            'pdf_id': f"pdf_{file_hash}",
            'pdf_title': pdf_path.stem,
            'file_path': str(pdf_path)
        }
        
        # Insert embeddings
        return self.insert_pdf_embeddings_to_supabase(pdf_data, chunks)
    
    def run_video_update(self, limit: int = 10) -> Tuple[int, int]:
        """
        Process new videos from Vimeo.
        
        Args:
            limit: Maximum number of videos to process
            
        Returns:
            Tuple of (total_videos_processed, total_embeddings_inserted)
        """
        logger.info("=== PROCESSING VIMEO VIDEOS ===")
        
        videos = self.fetch_new_videos_from_vimeo(limit)
        if not videos:
            logger.info("No videos to process")
            return 0, 0
        
        total_processed = 0
        total_embeddings = 0
        
        for video_data in videos:
            try:
                embeddings_count = self.process_video(video_data)
                if embeddings_count > 0:
                    total_processed += 1
                    total_embeddings += embeddings_count
            except Exception as e:
                logger.error(f"Error processing video {video_data.get('id', 'unknown')}: {e}")
                continue
        
        logger.info(f"Video processing complete: {total_processed} videos processed, {total_embeddings} embeddings inserted")
        return total_processed, total_embeddings
    
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
    
    def run(self, video_limit: int = 10) -> Dict[str, Any]:
        """
        Run the complete auto-update process.
        
        Args:
            video_limit: Maximum number of videos to process
            
        Returns:
            Summary of processing results
        """
        start_time = time.time()
        logger.info("Starting auto-update embeddings process...")
        
        # Process videos
        videos_processed, video_embeddings = self.run_video_update(video_limit)
        
        # Process PDFs
        pdfs_processed, pdf_embeddings = self.run_pdf_update()
        
        # Calculate totals
        total_processed = videos_processed + pdfs_processed
        total_embeddings = video_embeddings + pdf_embeddings
        processing_time = time.time() - start_time
        
        # Create summary
        summary = {
            'videos_processed': videos_processed,
            'video_embeddings_inserted': video_embeddings,
            'pdfs_processed': pdfs_processed,
            'pdf_embeddings_inserted': pdf_embeddings,
            'total_processed': total_processed,
            'total_embeddings_inserted': total_embeddings,
            'processing_time_seconds': round(processing_time, 2),
            'timestamp': datetime.now().isoformat()
        }
        
        logger.info("=== AUTO-UPDATE COMPLETE ===")
        logger.info(f"Videos processed: {videos_processed}")
        logger.info(f"Video embeddings inserted: {video_embeddings}")
        logger.info(f"PDFs processed: {pdfs_processed}")
        logger.info(f"PDF embeddings inserted: {pdf_embeddings}")
        logger.info(f"Total processing time: {processing_time:.2f} seconds")
        
        return summary

def main():
    """Main entry point for the auto-update script."""
    try:
        # Initialize auto-update system
        auto_update = AutoUpdateEmbeddings()
        
        # Run the update process
        summary = auto_update.run(video_limit=10)
        
        # Print summary
        print("\n" + "="*60)
        print("AUTO-UPDATE EMBEDDINGS SUMMARY")
        print("="*60)
        print(f"Videos processed: {summary['videos_processed']}")
        print(f"Video embeddings inserted: {summary['video_embeddings_inserted']}")
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
