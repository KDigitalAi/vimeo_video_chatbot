# Backend Configuration Guide

## Required Environment Variables

Your backend requires the following environment variables to function properly. Configure them in your `.env` file (for local development) or in Vercel's environment variables (for production).

### Critical Variables (Required for Chat)

```env
# OpenAI Configuration - REQUIRED
OPENAI_API_KEY=sk-...your-openai-api-key

# Supabase Configuration - REQUIRED
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-role-key

# Optional but Recommended
VIMEO_ACCESS_TOKEN=your-vimeo-token
```

### How to Get These Values

#### 1. OpenAI API Key
1. Go to https://platform.openai.com/api-keys
2. Sign in or create an account
3. Click "Create new secret key"
4. Copy the key (starts with `sk-`)
5. Add to your environment variables

#### 2. Supabase Configuration
1. Go to https://supabase.com
2. Create a new project or use existing
3. Go to Project Settings → API
4. Copy:
   - **Project URL** → `SUPABASE_URL`
   - **service_role key** (not anon key) → `SUPABASE_SERVICE_KEY`

#### 3. Vimeo Access Token (Optional)
1. Go to https://developer.vimeo.com/apps
2. Create an app
3. Generate an access token
4. Copy the token → `VIMEO_ACCESS_TOKEN`

## Setting Up Environment Variables

### For Local Development

Create a `.env` file in your project root:

```env
OPENAI_API_KEY=sk-your-key-here
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_KEY=your-service-key-here
VIMEO_ACCESS_TOKEN=your-token-here
ALLOWED_ORIGINS=http://localhost:3000,https://dev.chatbot.skillcapital.ai
ENVIRONMENT=development
```

### For Vercel Deployment

1. Go to your Vercel project dashboard
2. Click **Settings** → **Environment Variables**
3. Add each variable:
   - **Key**: `OPENAI_API_KEY`
   - **Value**: Your OpenAI API key
   - **Environment**: Production, Preview, Development (select all)
4. Repeat for all required variables
5. **Redeploy** your application after adding variables

## Verifying Configuration

### 1. Check Health Endpoint

Visit: `https://dev.chatbot.skillcapital.ai/health/detailed`

Expected response when configured correctly:
```json
{
  "status": "healthy",
  "services": {
    "openai": {
      "status": "available",
      "api_key": "configured"
    },
    "supabase": {
      "status": "available",
      "url": "configured",
      "key": "configured"
    }
  },
  "chat_service": {
    "schemas": {
      "status": "available"
    },
    "vector_store": {
      "status": "available"
    },
    "retriever_chain": {
      "status": "available"
    }
  }
}
```

### 2. Check Error Response

If you get a 503 error, the response now includes detailed diagnostics:

```json
{
  "error": "service_unavailable",
  "message": "Chat service is not properly configured. Please check server logs.",
  "missing_services": ["vector_store", "retriever_chain"],
  "missing_environment_variables": ["OPENAI_API_KEY", "SUPABASE_URL"],
  "guidance": "Missing required environment variables: OPENAI_API_KEY, SUPABASE_URL. Please configure these in your .env file or Vercel environment variables.",
  "timestamp": "2025-11-12T09:51:52.601007"
}
```

## Common Issues and Solutions

### Issue 1: "Missing required environment variables"

**Solution**: 
- Check that all variables are set in Vercel
- Ensure variable names match exactly (case-sensitive)
- Redeploy after adding variables
- Check `/health/detailed` to see which variables are missing

### Issue 2: "vector_store module not available"

**Solution**:
- This usually means Supabase credentials are incorrect
- Verify `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` are correct
- Ensure you're using the **service_role** key, not the **anon** key
- Check Supabase project is active and accessible

### Issue 3: "retriever_chain failed to import"

**Solution**:
- Usually indicates missing dependencies
- Check `requirements.txt` includes all LangChain packages
- Verify OpenAI API key is valid
- Check deployment logs for import errors

### Issue 4: "OpenAI API key is invalid"

**Solution**:
- Verify the API key starts with `sk-`
- Check the key hasn't expired or been revoked
- Ensure you have sufficient OpenAI credits
- Test the key at https://platform.openai.com

## Testing Configuration

### Quick Test Script

You can test your configuration locally:

```python
import os
from dotenv import load_dotenv

load_dotenv()

# Check required variables
required = [
    "OPENAI_API_KEY",
    "SUPABASE_URL", 
    "SUPABASE_SERVICE_KEY"
]

missing = []
for var in required:
    value = os.getenv(var)
    if not value:
        missing.append(var)
    else:
        print(f"✅ {var}: {'*' * 10} (configured)")

if missing:
    print(f"\n❌ Missing: {', '.join(missing)}")
else:
    print("\n✅ All required variables are configured!")
```

## Next Steps

1. **Set all environment variables** in Vercel
2. **Redeploy** your application
3. **Check `/health/detailed`** to verify all services are available
4. **Test chat endpoint** with a simple query
5. **Monitor logs** in Vercel dashboard if issues persist

## Support

If you continue to experience issues:

1. Check Vercel deployment logs: Dashboard → Deployments → Logs
2. Use `/debug/routers` endpoint to see router loading status
3. Check `/health/detailed` for service status
4. Review error messages - they now include specific guidance


