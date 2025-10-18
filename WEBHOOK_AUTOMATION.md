# Vimeo Webhook Automation System

This document describes the automated video processing system that handles new Vimeo video uploads and automatically stores their embeddings in Supabase.

## Overview

The webhook automation system automatically processes new Vimeo video uploads without manual intervention. When a new video is uploaded to your Vimeo account, the system:

1. **Detects** new video uploads via Vimeo webhooks
2. **Fetches** video metadata (title, description, duration, URL)
3. **Extracts** audio from the video using FFmpeg
4. **Transcribes** the audio into text using Whisper
5. **Chunks** the text into smaller segments
6. **Generates** embeddings for each chunk using the configured embedding model
7. **Stores** embeddings in the Supabase `video_embeddings` table

## Architecture

### Components

- **Webhook Endpoint**: `/webhooks/vimeo` - Receives Vimeo webhook notifications
- **Processing Pipeline**: Asynchronous background processing using FastAPI BackgroundTasks
- **Existing Modules**: Reuses `vimeo_loader.py`, `whisper_transcriber.py`, `text_processor.py`, `vector_store_direct.py`

### Data Flow

```
Vimeo Upload → Webhook → Background Task → Metadata Fetch → Audio Extraction → 
Transcription → Text Chunking → Embedding Generation → Supabase Storage
```

## Configuration

### Environment Variables

Add these to your `.env` file:

```env
# Required for webhook security
VIMEO_WEBHOOK_SECRET=your_webhook_secret_here

# Existing variables (already configured)
VIMEO_ACCESS_TOKEN=your_vimeo_token
OPENAI_API_KEY=your_openai_key
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_KEY=your_supabase_key
EMBEDDING_MODEL=text-embedding-3-small
```

### Vimeo Webhook Configuration

1. Go to your Vimeo Developer settings
2. Create a new webhook with these settings:
   - **URL**: `https://your-domain.com/webhooks/vimeo`
   - **Events**: Select `video.ready`, `video.transcoded`, `video.uploaded`
   - **Secret**: Set the same value as `VIMEO_WEBHOOK_SECRET` in your `.env`

## API Endpoints

### Webhook Endpoint

**POST** `/webhooks/vimeo`

Receives Vimeo webhook notifications and triggers automatic processing.

**Headers:**
- `Content-Type: application/json`
- `X-Webhook-Secret: your_webhook_secret` (if `VIMEO_WEBHOOK_SECRET` is set)

**Response:**
```json
{
  "status": "accepted",
  "video_id": "1234567890",
  "message": "Video processing pipeline started automatically",
  "webhook_type": "video.ready"
}
```

### Health Check

**GET** `/webhooks/health`

Check the status of the webhook system.

**Response:**
```json
{
  "status": "healthy",
  "webhook_system": "operational",
  "automatic_processing": "enabled",
  "supported_events": ["video.ready", "video.transcoded", "video.uploaded"]
}
```

### Manual Trigger (Testing)

**POST** `/webhooks/trigger/{video_id}`

Manually trigger video processing for testing purposes.

**Response:**
```json
{
  "status": "triggered",
  "video_id": "1234567890",
  "message": "Manual processing pipeline started",
  "note": "This is for testing purposes - use Vimeo webhooks in production"
}
```

## Processing Pipeline

### Step 1: Duplicate Check
- Checks if video already exists in `video_embeddings` table
- Skips processing if duplicate found to avoid reprocessing

### Step 2: Metadata Retrieval
- Fetches video metadata from Vimeo API
- Extracts title, duration, URL, and other relevant information
- Validates video access and permissions

### Step 3: Transcript Generation
- **Primary**: Attempts to retrieve existing captions from Vimeo
- **Fallback**: If no captions exist, extracts audio and transcribes with Whisper
- Handles both scenarios gracefully

### Step 4: Text Processing
- Chunks transcript text into manageable segments
- Preserves timestamp information for each chunk
- Applies configured chunk size and overlap settings

### Step 5: Embedding Generation
- Generates embeddings using the configured model (`text-embedding-3-small`)
- Creates vector representations for each text chunk
- Maintains consistency with existing embedding model

### Step 6: Database Storage
- Stores embeddings in Supabase `video_embeddings` table
- Includes all required fields: `id`, `content`, `embedding`, `video_id`, `video_title`, `chunk_id`, `timestamp_start`, `timestamp_end`
- Uses batch insertion for efficiency

## Error Handling

The system includes comprehensive error handling:

- **Webhook Failures**: Logs errors but doesn't fail the webhook response
- **Processing Failures**: Logs detailed error information and continues processing other videos
- **Duplicate Detection**: Gracefully skips already processed videos
- **API Failures**: Handles Vimeo API, OpenAI API, and Supabase connection issues
- **Transcription Failures**: Logs errors and continues with next video

## Logging

The system provides detailed logging with emojis for easy identification:

- 🎬 New video detected
- 📋 Duplicate check
- 📊 Metadata retrieval
- 📝 Caption retrieval
- 🎵 Audio extraction
- ✂️ Text chunking
- 🧠 Embedding generation
- 🎉 Success completion
- ❌ Error conditions
- ⚠️ Warnings

## Testing

### Manual Testing

1. **Health Check**:
   ```bash
   curl http://localhost:8000/webhooks/health
   ```

2. **Manual Trigger**:
   ```bash
   curl -X POST http://localhost:8000/webhooks/trigger/VIDEO_ID
   ```

3. **Webhook Simulation**:
   ```bash
   curl -X POST http://localhost:8000/webhooks/vimeo \
     -H "Content-Type: application/json" \
     -d '{"type": "video.ready", "clip": {"uri": "/videos/VIDEO_ID"}}'
   ```

### Production Testing

1. Upload a new video to your Vimeo account
2. Check the logs for processing messages
3. Verify embeddings appear in the `video_embeddings` table
4. Test the chatbot with questions about the new video

## Monitoring

### Log Monitoring

Monitor the application logs for:
- Webhook reception messages
- Processing pipeline progress
- Error conditions
- Success confirmations

### Database Monitoring

Check the `video_embeddings` table for:
- New video entries
- Correct embedding generation
- Proper metadata storage

## Security

### Webhook Security

- **Secret Validation**: Optional webhook secret validation
- **HTTPS Only**: Webhooks should only be sent to HTTPS endpoints
- **IP Whitelisting**: Consider whitelisting Vimeo's IP ranges

### API Security

- **Authentication**: Uses Vimeo access token for API calls
- **Rate Limiting**: Built-in rate limiting for API calls
- **Error Handling**: Doesn't expose sensitive information in error responses

## Troubleshooting

### Common Issues

1. **Webhook Not Triggered**:
   - Check Vimeo webhook configuration
   - Verify webhook URL is accessible
   - Check webhook secret configuration

2. **Processing Failures**:
   - Check Vimeo API access token
   - Verify OpenAI API key
   - Check Supabase connection

3. **Duplicate Processing**:
   - System automatically prevents duplicates
   - Check `video_embeddings` table for existing entries

### Debug Mode

Enable debug logging by setting:
```env
DEBUG=true
```

## Performance

### Optimization Features

- **Asynchronous Processing**: Non-blocking webhook responses
- **Background Tasks**: Processing runs in background
- **Batch Operations**: Efficient database operations
- **Duplicate Prevention**: Avoids unnecessary reprocessing

### Scaling Considerations

- **Concurrent Processing**: Multiple videos can be processed simultaneously
- **Resource Management**: Efficient memory and CPU usage
- **Database Optimization**: Batch insertions and proper indexing

## Maintenance

### Regular Tasks

1. **Monitor Logs**: Check for processing errors
2. **Database Cleanup**: Remove old temporary files
3. **API Quotas**: Monitor Vimeo and OpenAI API usage
4. **Webhook Health**: Verify webhook endpoint accessibility

### Updates

- **Model Updates**: Update embedding model as needed
- **API Changes**: Monitor Vimeo API changes
- **Dependencies**: Keep dependencies updated

## Support

For issues or questions:

1. Check the application logs
2. Verify configuration settings
3. Test with manual trigger endpoint
4. Review this documentation

The webhook automation system is designed to be robust, efficient, and maintainable while providing comprehensive logging and error handling.
