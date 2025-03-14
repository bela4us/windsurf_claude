<<<<<<< HEAD
from typing import Any, Dict, List, Optional, Union
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import multiprocessing
from functools import partial
import logging
from datetime import datetime
import json
import orjson
from memory_profiler import profile

logger = logging.getLogger(__name__)

class DataProcessor:
    def __init__(self, max_workers: Optional[int] = None):
        self.max_workers = max_workers or multiprocessing.cpu_count()
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        
    @profile
    def process_dataframe(self,
                         df: pd.DataFrame,
                         operations: List[Dict[str, Any]]) -> pd.DataFrame:
        """Procesira DataFrame s optimiziranim operacijama"""
        try:
            for op in operations:
                if op['type'] == 'filter':
                    df = self._apply_filter(df, op['conditions'])
                elif op['type'] == 'transform':
                    df = self._apply_transform(df, op['function'])
                elif op['type'] == 'aggregate':
                    df = self._apply_aggregation(df, op['group_by'], op['agg_funcs'])
            return df
        except Exception as e:
            logger.error(f"Error processing DataFrame: {str(e)}")
            raise
    
    def _apply_filter(self, df: pd.DataFrame, conditions: Dict) -> pd.DataFrame:
        """Primjenjuje filter na DataFrame"""
        mask = pd.Series(True, index=df.index)
        for col, condition in conditions.items():
            if isinstance(condition, dict):
                if condition['operator'] == '>':
                    mask &= df[col] > condition['value']
                elif condition['operator'] == '<':
                    mask &= df[col] < condition['value']
                elif condition['operator'] == '==':
                    mask &= df[col] == condition['value']
        return df[mask]
    
    def _apply_transform(self, df: pd.DataFrame, func: Callable) -> pd.DataFrame:
        """Primjenjuje transformaciju na DataFrame"""
        return func(df)
    
    def _apply_aggregation(self,
                          df: pd.DataFrame,
                          group_by: List[str],
                          agg_funcs: Dict[str, List[str]]) -> pd.DataFrame:
        """Primjenjuje agregaciju na DataFrame"""
        return df.groupby(group_by).agg(agg_funcs)
    
    def parallel_process(self,
                        data: List[Any],
                        process_func: Callable,
                        chunk_size: int = 1000) -> List[Any]:
        """Paralelno procesira podatke"""
        chunks = [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]
        results = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(process_func, chunk) for chunk in chunks]
            for future in futures:
                results.extend(future.result())
        return results
    
    def optimize_memory(self, df: pd.DataFrame) -> pd.DataFrame:
        """Optimizira memorijsku upotrebu DataFrame-a"""
        for col in df.columns:
            if df[col].dtype == 'float64':
                df[col] = pd.to_numeric(df[col], downcast='float')
            elif df[col].dtype == 'int64':
                df[col] = pd.to_numeric(df[col], downcast='integer')
            elif df[col].dtype == 'object':
                if df[col].nunique() / len(df) < 0.5:
                    df[col] = df[col].astype('category')
        return df
    
    def fast_json_serialize(self, data: Any) -> bytes:
        """Brzo serijalizira podatke u JSON koristeći orjson"""
        return orjson.dumps(data)
    
    def fast_json_deserialize(self, data: bytes) -> Any:
        """Brzo deserijalizira JSON podatke koristeći orjson"""
        return orjson.loads(data)
    
    def cache_data(self,
                  data: Any,
                  cache_key: str,
                  ttl: int = 3600) -> None:
        """Sprema podatke u cache"""
        try:
            serialized_data = self.fast_json_serialize(data)
            # Implementacija cache-a ovisi o korištenom cache sustavu
            # Ovdje je primjer za Redis:
            # redis_client.setex(cache_key, ttl, serialized_data)
            pass
        except Exception as e:
            logger.error(f"Error caching data: {str(e)}")
    
    def get_cached_data(self, cache_key: str) -> Optional[Any]:
        """Dohvaća podatke iz cache-a"""
        try:
            # Implementacija dohvata iz cache-a
            # cached_data = redis_client.get(cache_key)
            # if cached_data:
            #     return self.fast_json_deserialize(cached_data)
            return None
        except Exception as e:
            logger.error(f"Error getting cached data: {str(e)}")
            return None
    
    def batch_process(self,
                     data: List[Any],
                     process_func: Callable,
                     batch_size: int = 100) -> List[Any]:
        """Procesira podatke u batch-evima"""
        results = []
        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            batch_results = process_func(batch)
            results.extend(batch_results)
        return results
    
    def monitor_performance(self, func: Callable) -> Callable:
        """Dekorator za praćenje performansi funkcije"""
        def wrapper(*args, **kwargs):
            start_time = datetime.now()
            result = func(*args, **kwargs)
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            logger.info(f"Function {func.__name__} took {duration:.2f} seconds")
            return result
        return wrapper
    
    def shutdown(self):
        """Zatvara executor"""
=======
from typing import Any, Dict, List, Optional, Union
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import multiprocessing
from functools import partial
import logging
from datetime import datetime
import json
import orjson
from memory_profiler import profile

logger = logging.getLogger(__name__)

class DataProcessor:
    def __init__(self, max_workers: Optional[int] = None):
        self.max_workers = max_workers or multiprocessing.cpu_count()
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        
    @profile
    def process_dataframe(self,
                         df: pd.DataFrame,
                         operations: List[Dict[str, Any]]) -> pd.DataFrame:
        """Procesira DataFrame s optimiziranim operacijama"""
        try:
            for op in operations:
                if op['type'] == 'filter':
                    df = self._apply_filter(df, op['conditions'])
                elif op['type'] == 'transform':
                    df = self._apply_transform(df, op['function'])
                elif op['type'] == 'aggregate':
                    df = self._apply_aggregation(df, op['group_by'], op['agg_funcs'])
            return df
        except Exception as e:
            logger.error(f"Error processing DataFrame: {str(e)}")
            raise
    
    def _apply_filter(self, df: pd.DataFrame, conditions: Dict) -> pd.DataFrame:
        """Primjenjuje filter na DataFrame"""
        mask = pd.Series(True, index=df.index)
        for col, condition in conditions.items():
            if isinstance(condition, dict):
                if condition['operator'] == '>':
                    mask &= df[col] > condition['value']
                elif condition['operator'] == '<':
                    mask &= df[col] < condition['value']
                elif condition['operator'] == '==':
                    mask &= df[col] == condition['value']
        return df[mask]
    
    def _apply_transform(self, df: pd.DataFrame, func: Callable) -> pd.DataFrame:
        """Primjenjuje transformaciju na DataFrame"""
        return func(df)
    
    def _apply_aggregation(self,
                          df: pd.DataFrame,
                          group_by: List[str],
                          agg_funcs: Dict[str, List[str]]) -> pd.DataFrame:
        """Primjenjuje agregaciju na DataFrame"""
        return df.groupby(group_by).agg(agg_funcs)
    
    def parallel_process(self,
                        data: List[Any],
                        process_func: Callable,
                        chunk_size: int = 1000) -> List[Any]:
        """Paralelno procesira podatke"""
        chunks = [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]
        results = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(process_func, chunk) for chunk in chunks]
            for future in futures:
                results.extend(future.result())
        return results
    
    def optimize_memory(self, df: pd.DataFrame) -> pd.DataFrame:
        """Optimizira memorijsku upotrebu DataFrame-a"""
        for col in df.columns:
            if df[col].dtype == 'float64':
                df[col] = pd.to_numeric(df[col], downcast='float')
            elif df[col].dtype == 'int64':
                df[col] = pd.to_numeric(df[col], downcast='integer')
            elif df[col].dtype == 'object':
                if df[col].nunique() / len(df) < 0.5:
                    df[col] = df[col].astype('category')
        return df
    
    def fast_json_serialize(self, data: Any) -> bytes:
        """Brzo serijalizira podatke u JSON koristeći orjson"""
        return orjson.dumps(data)
    
    def fast_json_deserialize(self, data: bytes) -> Any:
        """Brzo deserijalizira JSON podatke koristeći orjson"""
        return orjson.loads(data)
    
    def cache_data(self,
                  data: Any,
                  cache_key: str,
                  ttl: int = 3600) -> None:
        """Sprema podatke u cache"""
        try:
            serialized_data = self.fast_json_serialize(data)
            # Implementacija cache-a ovisi o korištenom cache sustavu
            # Ovdje je primjer za Redis:
            # redis_client.setex(cache_key, ttl, serialized_data)
            pass
        except Exception as e:
            logger.error(f"Error caching data: {str(e)}")
    
    def get_cached_data(self, cache_key: str) -> Optional[Any]:
        """Dohvaća podatke iz cache-a"""
        try:
            # Implementacija dohvata iz cache-a
            # cached_data = redis_client.get(cache_key)
            # if cached_data:
            #     return self.fast_json_deserialize(cached_data)
            return None
        except Exception as e:
            logger.error(f"Error getting cached data: {str(e)}")
            return None
    
    def batch_process(self,
                     data: List[Any],
                     process_func: Callable,
                     batch_size: int = 100) -> List[Any]:
        """Procesira podatke u batch-evima"""
        results = []
        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            batch_results = process_func(batch)
            results.extend(batch_results)
        return results
    
    def monitor_performance(self, func: Callable) -> Callable:
        """Dekorator za praćenje performansi funkcije"""
        def wrapper(*args, **kwargs):
            start_time = datetime.now()
            result = func(*args, **kwargs)
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            logger.info(f"Function {func.__name__} took {duration:.2f} seconds")
            return result
        return wrapper
    
    def shutdown(self):
        """Zatvara executor"""
>>>>>>> c45eb88e3e23e6f6a3bf252c5a572f1c5cdb8266
        self.executor.shutdown(wait=True) 