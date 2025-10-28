"""
Connection pooling for database and external services.
"""
import asyncio
from typing import Optional
from functools import lru_cache
from backend.core.settings import settings

class ConnectionPool:
    """Connection pool manager."""
    
    def __init__(self, max_connections: int = 10):
        self.max_connections = max_connections
        self._pool = asyncio.Queue(maxsize=max_connections)
        self._created_connections = 0
    
    async def get_connection(self):
        """Get connection from pool."""
        if not self._pool.empty():
            return await self._pool.get()
        
        if self._created_connections < self.max_connections:
            # Create new connection
            connection = await self._create_connection()
            self._created_connections += 1
            return connection
        
        # Wait for available connection
        return await self._pool.get()
    
    async def return_connection(self, connection):
        """Return connection to pool."""
        await self._pool.put(connection)
    
    async def _create_connection(self):
        """Create new connection (implement based on your needs)."""
        # This would create actual connections
        pass

# Global connection pools
supabase_pool = ConnectionPool(max_connections=5)
openai_pool = ConnectionPool(max_connections=3)
