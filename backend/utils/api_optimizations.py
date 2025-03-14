from django.core.cache import cache
from django.http import JsonResponse
from django.core.paginator import Paginator
from typing import Any, Dict, List, Optional
import logging
from functools import wraps
import json
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)

class APIOptimizer:
    def __init__(self):
        self.default_cache_ttl = 300  # 5 minuta
        self.default_page_size = 20
        self.max_page_size = 100

    def cache_response(self, ttl: Optional[int] = None):
        """Dekorator za keširanje API odgovora"""
        def decorator(view_func):
            @wraps(view_func)
            def wrapper(request, *args, **kwargs):
                # Generiraj cache key
                cache_key = f"api:{request.path}:{json.dumps(request.GET)}"
                
                # Provjeri cache
                cached_response = cache.get(cache_key)
                if cached_response:
                    return JsonResponse(cached_response)
                
                # Izvrši view
                response = view_func(request, *args, **kwargs)
                
                # Spremi u cache
                if isinstance(response, JsonResponse):
                    cache.set(cache_key, response.json(), ttl or self.default_cache_ttl)
                else:
                    cache.set(cache_key, response, ttl or self.default_cache_ttl)
                
                return response
            return wrapper
        return decorator

    def paginate_response(self, queryset: List[Any], request) -> Dict[str, Any]:
        """Paginiraj response"""
        try:
            page = request.GET.get('page', 1)
            page_size = min(
                int(request.GET.get('page_size', self.default_page_size)),
                self.max_page_size
            )
            
            paginator = Paginator(queryset, page_size)
            page_obj = paginator.get_page(page)
            
            return {
                'count': paginator.count,
                'total_pages': paginator.num_pages,
                'current_page': page_obj.number,
                'results': list(page_obj)
            }
        except Exception as e:
            logger.error(f"Greška pri paginaciji: {e}")
            return {
                'count': len(queryset),
                'total_pages': 1,
                'current_page': 1,
                'results': queryset
            }

    def compress_response(self, response: Response) -> Response:
        """Kompresiraj response ako je velik"""
        try:
            if len(json.dumps(response.data)) > 1024:  # 1KB
                response.data = {
                    'compressed': True,
                    'data': response.data
                }
            return response
        except Exception as e:
            logger.error(f"Greška pri kompresiji response-a: {e}")
            return response

    def version_api(self, version: str):
        """Dekorator za verzioniranje API-ja"""
        def decorator(view_class):
            class VersionedView(view_class):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, **kwargs)
                    self.version = version
                
                def dispatch(self, request, *args, **kwargs):
                    request.version = self.version
                    return super().dispatch(request, *args, **kwargs)
            return VersionedView
        return decorator

    def rate_limit(self, requests_per_minute: int):
        """Dekorator za rate limiting"""
        def decorator(view_func):
            @wraps(view_func)
            def wrapper(request, *args, **kwargs):
                # Implementacija rate limitinga
                # Ovo je pojednostavljena verzija, trebalo bi koristiti Redis
                key = f"rate_limit:{request.META.get('REMOTE_ADDR')}:{request.path}"
                current = cache.get(key, 0)
                
                if current >= requests_per_minute:
                    return Response(
                        {'error': 'Rate limit exceeded'},
                        status=status.HTTP_429_TOO_MANY_REQUESTS
                    )
                
                cache.set(key, current + 1, 60)
                return view_func(request, *args, **kwargs)
            return wrapper
        return decorator

    def validate_request(self, schema: Dict[str, Any]):
        """Dekorator za validaciju requesta"""
        def decorator(view_func):
            @wraps(view_func)
            def wrapper(request, *args, **kwargs):
                try:
                    # Validacija prema shemi
                    for field, rules in schema.items():
                        if field not in request.data:
                            if rules.get('required', False):
                                return Response(
                                    {'error': f'Missing required field: {field}'},
                                    status=status.HTTP_400_BAD_REQUEST
                                )
                        else:
                            # Dodatna validacija prema tipu
                            if not isinstance(request.data[field], rules.get('type', type(None))):
                                return Response(
                                    {'error': f'Invalid type for field: {field}'},
                                    status=status.HTTP_400_BAD_REQUEST
                                )
                    
                    return view_func(request, *args, **kwargs)
                except Exception as e:
                    logger.error(f"Greška pri validaciji requesta: {e}")
                    return Response(
                        {'error': 'Invalid request'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            return wrapper
        return decorator

# Inicijalizacija optimizatora
api_optimizer = APIOptimizer() 