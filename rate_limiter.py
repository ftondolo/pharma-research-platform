# backend/rate_limiter.py

import os
import redis
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self):
        self.redis_client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
        
        # Conservative limits to avoid quota issues
        self.limits = {
            'embeddings': {
                'per_minute': int(os.getenv("EMBEDDINGS_PER_MINUTE", "50")),
                'per_hour': int(os.getenv("EMBEDDINGS_PER_HOUR", "1000")),
                'per_day': int(os.getenv("EMBEDDINGS_PER_DAY", "5000"))
            },
            'completions': {
                'per_minute': int(os.getenv("COMPLETIONS_PER_MINUTE", "10")),
                'per_hour': int(os.getenv("COMPLETIONS_PER_HOUR", "100")),
                'per_day': int(os.getenv("COMPLETIONS_PER_DAY", "500"))
            }
        }
        
        # Cost tracking
        self.costs = {
            'text-embedding-ada-002': 0.0001,  # per 1K tokens
            'text-embedding-3-small': 0.00002,  # per 1K tokens
            'text-embedding-3-large': 0.00013,  # per 1K tokens
            'gpt-3.5-turbo': 0.0005,  # per 1K tokens
            'gpt-4': 0.03  # per 1K tokens
        }
    
    async def can_make_request(self, request_type: str) -> bool:
        """Check if we can make a request without exceeding limits"""
        try:
            now = datetime.now()
            
            # Check minute limit
            minute_key = f"rate:{request_type}:minute:{now.strftime('%Y%m%d%H%M')}"
            minute_count = self.redis_client.get(minute_key)
            minute_count = int(minute_count) if minute_count else 0
            
            if minute_count >= self.limits[request_type]['per_minute']:
                logger.warning(f"Minute rate limit reached for {request_type}: {minute_count}")
                return False
            
            # Check hour limit
            hour_key = f"rate:{request_type}:hour:{now.strftime('%Y%m%d%H')}"
            hour_count = self.redis_client.get(hour_key)
            hour_count = int(hour_count) if hour_count else 0
            
            if hour_count >= self.limits[request_type]['per_hour']:
                logger.warning(f"Hour rate limit reached for {request_type}: {hour_count}")
                return False
            
            # Check day limit
            day_key = f"rate:{request_type}:day:{now.strftime('%Y%m%d')}"
            day_count = self.redis_client.get(day_key)
            day_count = int(day_count) if day_count else 0
            
            if day_count >= self.limits[request_type]['per_day']:
                logger.warning(f"Day rate limit reached for {request_type}: {day_count}")
                return False
            
            # Increment counters
            pipe = self.redis_client.pipeline()
            pipe.incr(minute_key)
            pipe.expire(minute_key, 60)
            pipe.incr(hour_key)
            pipe.expire(hour_key, 3600)
            pipe.incr(day_key)
            pipe.expire(day_key, 86400)
            pipe.execute()
            
            return True
            
        except Exception as e:
            logger.error(f"Rate limiter error: {e}")
            # Be conservative - don't make request if rate limiter fails
            return False
    
    async def get_usage_stats(self) -> Dict:
        """Get current usage statistics"""
        try:
            now = datetime.now()
            stats = {}
            
            for request_type in self.limits:
                minute_key = f"rate:{request_type}:minute:{now.strftime('%Y%m%d%H%M')}"
                hour_key = f"rate:{request_type}:hour:{now.strftime('%Y%m%d%H')}"
                day_key = f"rate:{request_type}:day:{now.strftime('%Y%m%d')}"
                
                minute_count = self.redis_client.get(minute_key)
                hour_count = self.redis_client.get(hour_key)
                day_count = self.redis_client.get(day_key)
                
                stats[request_type] = {
                    'minute': {
                        'used': int(minute_count) if minute_count else 0,
                        'limit': self.limits[request_type]['per_minute']
                    },
                    'hour': {
                        'used': int(hour_count) if hour_count else 0,
                        'limit': self.limits[request_type]['per_hour']
                    },
                    'day': {
                        'used': int(day_count) if day_count else 0,
                        'limit': self.limits[request_type]['per_day']
                    }
                }
            
            # Get monthly cost estimate
            month_key = f"cost:{now.strftime('%Y%m')}"
            monthly_cost = self.redis_client.get(month_key)
            stats['estimated_monthly_cost'] = float(monthly_cost) if monthly_cost else 0.0
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting usage stats: {e}")
            return {}
    
    async def track_cost(self, model: str, tokens: int):
        """Track API costs"""
        try:
            if model in self.costs:
                cost = (tokens / 1000) * self.costs[model]
                month_key = f"cost:{datetime.now().strftime('%Y%m')}"
                self.redis_client.incrbyfloat(month_key, cost)
                self.redis_client.expire(month_key, 86400 * 31)  # Keep for 31 days
        except Exception as e:
            logger.error(f"Error tracking cost: {e}")

# Singleton instance
rate_limiter = RateLimiter()
