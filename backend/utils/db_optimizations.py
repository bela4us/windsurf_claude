from django.db import connection
from django.core.cache import cache
from django.db.models import QuerySet
from typing import List, Any, Dict
import logging
from functools import wraps
import time
from django.db.models import Avg, Count, Sum
from django.db.models.functions import TruncDate
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

logger = logging.getLogger(__name__)

class DatabaseOptimizer:
    def __init__(self):
        self.connection_pool = {}
        self.max_connections = 10
        self.query_cache_ttl = 300  # 5 minuta
        self.bulk_size = 1000
        self.indexes = {}
        self.query_stats = {}

    def get_connection(self):
        """Dohvati konekciju iz pool-a"""
        if len(self.connection_pool) < self.max_connections:
            conn = connection
            self.connection_pool[id(conn)] = conn
            return conn
        return min(self.connection_pool.values(), key=lambda x: x._connection_created)

    def cache_query(self, cache_key: str, ttl: int = None):
        """Dekorator za keširanje query rezultata"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Provjeri cache
                cached_result = cache.get(cache_key)
                if cached_result is not None:
                    return cached_result

                # Izvrši query
                result = func(*args, **kwargs)
                
                # Spremi u cache
                cache.set(cache_key, result, ttl or self.query_cache_ttl)
                return result
            return wrapper
        return decorator

    def bulk_create(self, model_class, objects: List[Any]) -> List[Any]:
        """Optimizirano bulk kreiranje objekata"""
        try:
            # Podijeli objekte u batch-eve
            for i in range(0, len(objects), self.bulk_size):
                batch = objects[i:i + self.bulk_size]
                model_class.objects.bulk_create(batch)
            
            return objects
        except Exception as e:
            logger.error(f"Greška pri bulk create: {e}")
            raise

    def bulk_update(self, objects: List[Any], fields: List[str]) -> int:
        """Optimizirano bulk ažuriranje objekata"""
        try:
            count = 0
            for i in range(0, len(objects), self.bulk_size):
                batch = objects[i:i + self.bulk_size]
                count += len(batch)
                type(objects[0]).objects.bulk_update(batch, fields)
            return count
        except Exception as e:
            logger.error(f"Greška pri bulk update: {e}")
            raise

    def bulk_delete(self, queryset: QuerySet) -> int:
        """Optimizirano bulk brisanje objekata"""
        try:
            count = queryset.count()
            queryset.delete()
            return count
        except Exception as e:
            logger.error(f"Greška pri bulk delete: {e}")
            raise

    def optimize_query(self, queryset: QuerySet) -> QuerySet:
        """Optimiziraj query"""
        try:
            # Dodaj select_related za foreign key veze
            if hasattr(queryset.model, '_meta'):
                for field in queryset.model._meta.get_fields():
                    if field.is_relation and not field.many_to_many:
                        queryset = queryset.select_related(field.name)
            
            # Dodaj prefetch_related za many-to-many veze
            for field in queryset.model._meta.get_fields():
                if field.many_to_many:
                    queryset = queryset.prefetch_related(field.name)
            
            return queryset
        except Exception as e:
            logger.error(f"Greška pri optimizaciji query-a: {e}")
            return queryset

    def create_index(self, model_class, fields: List[str], name: str = None):
        """Kreiraj indeks na navedenim poljima"""
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                if not name:
                    name = f"idx_{'_'.join(fields)}"
                
                fields_str = ", ".join(fields)
                cursor.execute(f"""
                    CREATE INDEX IF NOT EXISTS {name}
                    ON {model_class._meta.db_table} ({fields_str})
                """)
                
                self.indexes[name] = {
                    'model': model_class,
                    'fields': fields
                }
        except Exception as e:
            logger.error(f"Greška pri kreiranju indeksa: {e}")
            raise

    def analyze_query(self, queryset: QuerySet) -> Dict[str, Any]:
        """Analiziraj query performanse"""
        try:
            start_time = time.time()
            result = list(queryset)
            execution_time = time.time() - start_time
            
            return {
                'execution_time': execution_time,
                'row_count': len(result),
                'query': str(queryset.query),
                'explain': queryset.explain()
            }
        except Exception as e:
            logger.error(f"Greška pri analizi query-a: {e}")
            return {}

    def optimize_aggregations(self, queryset: QuerySet) -> QuerySet:
        """Optimiziraj agregacijske upite"""
        try:
            # Dodaj annotacije za česte agregacije
            queryset = queryset.annotate(
                daily_count=Count('id', filter=TruncDate('created_at')),
                daily_sum=Sum('value', filter=TruncDate('created_at')),
                daily_avg=Avg('value', filter=TruncDate('created_at'))
            )
            return queryset
        except Exception as e:
            logger.error(f"Greška pri optimizaciji agregacija: {e}")
            return queryset

    def track_query_stats(self, query: str, execution_time: float):
        """Praćenje statistike upita"""
        try:
            if query not in self.query_stats:
                self.query_stats[query] = {
                    'count': 0,
                    'total_time': 0,
                    'avg_time': 0
                }
            
            stats = self.query_stats[query]
            stats['count'] += 1
            stats['total_time'] += execution_time
            stats['avg_time'] = stats['total_time'] / stats['count']
            
            # Spremi statistiku u cache
            cache.set(f"query_stats:{query}", stats, 3600)
            
        except Exception as e:
            logger.error(f"Greška pri praćenju statistike upita: {e}")

    def cleanup_old_data(self, model_class, field: str, days: int):
        """Čišćenje starih podataka"""
        try:
            from django.utils import timezone
            cutoff_date = timezone.now() - timezone.timedelta(days=days)
            
            old_data = model_class.objects.filter(
                **{f"{field}__lt": cutoff_date}
            )
            
            count = old_data.count()
            old_data.delete()
            
            logger.info(f"Obrisano {count} starih zapisa iz {model_class.__name__}")
            return count
            
        except Exception as e:
            logger.error(f"Greška pri čišćenju starih podataka: {e}")
            raise

# Inicijalizacija optimizatora
db_optimizer = DatabaseOptimizer()

# Signal handleri za automatsko ažuriranje keša
@receiver(post_save)
def invalidate_cache(sender, instance, **kwargs):
    """Invalidiraj keš nakon promjene modela"""
    try:
        cache_key = f"{sender.__name__}:{instance.id}"
        cache.delete(cache_key)
    except Exception as e:
        logger.error(f"Greška pri invalidaciji keša: {e}")

@receiver(post_delete)
def cleanup_cache(sender, instance, **kwargs):
    """Očisti keš nakon brisanja modela"""
    try:
        cache_key = f"{sender.__name__}:{instance.id}"
        cache.delete(cache_key)
    except Exception as e:
        logger.error(f"Greška pri čišćenju keša: {e}") 