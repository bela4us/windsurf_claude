from typing import Dict, Any, Optional, List, Callable, Union
import pandas as pd
import numpy as np
import threading
from datetime import datetime
from dataclasses import dataclass
import asyncio
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import logging
from pathlib import Path
import json
import orjson
import gc
from functools import wraps, partial
import psutil
import memory_profiler
import pickle
import msgpack
import time

logger = logging.getLogger(__name__)

@dataclass
class DataStats:
    total_rows: int = 0
    total_columns: int = 0
    memory_usage: int = 0
    processing_time: float = 0.0
    last_optimization: Optional[datetime] = None

class DataManager:
    def __init__(
        self,
        max_workers: int = 4,
        chunk_size: int = 10000,
        compression: str = "gzip",
        optimize_memory: bool = True
    ):
        self.logger = logging.getLogger(__name__)
        self.max_workers = max_workers
        self.chunk_size = chunk_size
        self.compression = compression
        self.optimize_memory = optimize_memory
        
        self.thread_pool = ThreadPoolExecutor(max_workers=max_workers)
        self.process_pool = ProcessPoolExecutor(max_workers=max_workers)
        self.stats = DataStats()
        
    def optimize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Optimizira DataFrame za manje korištenje memorije."""
        try:
            start_time = time.time()
            
            # Optimiziraj tipove podataka
            for col in df.columns:
                col_type = df[col].dtype
                
                if col_type != object:
                    c_min = df[col].min()
                    c_max = df[col].max()
                    
                    if str(col_type)[:3] == "int":
                        if c_min >= np.iinfo(np.int8).min and c_max <= np.iinfo(np.int8).max:
                            df[col] = df[col].astype(np.int8)
                        elif c_min >= np.iinfo(np.int16).min and c_max <= np.iinfo(np.int16).max:
                            df[col] = df[col].astype(np.int16)
                        elif c_min >= np.iinfo(np.int32).min and c_max <= np.iinfo(np.int32).max:
                            df[col] = df[col].astype(np.int32)
                        elif c_min >= np.iinfo(np.int64).min and c_max <= np.iinfo(np.int64).max:
                            df[col] = df[col].astype(np.int64)
                            
                    elif str(col_type)[:5] == "float":
                        if c_min >= np.finfo(np.float16).min and c_max <= np.finfo(np.float16).max:
                            df[col] = df[col].astype(np.float16)
                        elif c_min >= np.finfo(np.float32).min and c_max <= np.finfo(np.float32).max:
                            df[col] = df[col].astype(np.float32)
                        else:
                            df[col] = df[col].astype(np.float64)
                            
            # Optimiziraj object tipove
            for col in df.select_dtypes(include=["object"]).columns:
                if df[col].nunique() / len(df) < 0.5:
                    df[col] = df[col].astype("category")
                    
            # Optimiziraj datetime tipove
            for col in df.select_dtypes(include=["datetime64"]).columns:
                df[col] = pd.to_datetime(df[col]).dt.tz_localize(None)
                
            processing_time = time.time() - start_time
            self.stats.processing_time += processing_time
            self.stats.last_optimization = datetime.now()
            
            return df
            
        except Exception as e:
            self.logger.error(f"Greška pri optimizaciji DataFrame-a: {e}")
            return df
            
    def process_dataframe(
        self,
        df: pd.DataFrame,
        func: callable,
        chunks: bool = True
    ) -> pd.DataFrame:
        """Procesira DataFrame paralelno."""
        try:
            start_time = time.time()
            
            if chunks:
                # Procesiraj u chunkovima
                chunk_size = len(df) // self.max_workers
                chunks = [df[i:i + chunk_size] for i in range(0, len(df), chunk_size)]
                
                with self.process_pool as executor:
                    results = list(executor.map(func, chunks))
                    
                result = pd.concat(results, ignore_index=True)
                
            else:
                # Procesiraj cijeli DataFrame
                with self.process_pool as executor:
                    result = executor.submit(func, df).result()
                    
            processing_time = time.time() - start_time
            self.stats.processing_time += processing_time
            
            return result
            
        except Exception as e:
            self.logger.error(f"Greška pri procesiranju DataFrame-a: {e}")
            return df
            
    def fast_json_serialize(self, data: Any) -> bytes:
        """Brza JSON serijalizacija s orjson."""
        try:
            return orjson.dumps(data)
        except Exception as e:
            self.logger.error(f"Greška pri JSON serijalizaciji: {e}")
            return json.dumps(data).encode()
            
    def fast_json_deserialize(self, data: bytes) -> Any:
        """Brza JSON deserijalizacija s orjson."""
        try:
            return orjson.loads(data)
        except Exception as e:
            self.logger.error(f"Greška pri JSON deserijalizaciji: {e}")
            return json.loads(data.decode())
            
    def msgpack_serialize(self, data: Any) -> bytes:
        """Serijalizacija s MessagePack."""
        try:
            return msgpack.packb(data)
        except Exception as e:
            self.logger.error(f"Greška pri MessagePack serijalizaciji: {e}")
            return pickle.dumps(data)
            
    def msgpack_deserialize(self, data: bytes) -> Any:
        """Deserijalizacija s MessagePack."""
        try:
            return msgpack.unpackb(data)
        except Exception as e:
            self.logger.error(f"Greška pri MessagePack deserijalizaciji: {e}")
            return pickle.loads(data)
            
    def batch_process(
        self,
        items: List[Any],
        func: callable,
        batch_size: Optional[int] = None
    ) -> List[Any]:
        """Procesira stavke u batchovima."""
        try:
            if batch_size is None:
                batch_size = self.chunk_size
                
            results = []
            for i in range(0, len(items), batch_size):
                batch = items[i:i + batch_size]
                with self.thread_pool as executor:
                    batch_results = list(executor.map(func, batch))
                results.extend(batch_results)
                
            return results
            
        except Exception as e:
            self.logger.error(f"Greška pri batch procesiranju: {e}")
            return []
            
    def get_stats(self) -> DataStats:
        """Dohvaća statistiku podataka."""
        return self.stats
        
    def monitor(self) -> Dict[str, Any]:
        """Praći stanje podataka."""
        try:
            return {
                "total_rows": self.stats.total_rows,
                "total_columns": self.stats.total_columns,
                "memory_usage": self.stats.memory_usage,
                "processing_time": self.stats.processing_time,
                "last_optimization": self.stats.last_optimization,
                "thread_pool_active": self.thread_pool._threads,
                "process_pool_active": len(self.process_pool._processes)
            }
            
        except Exception as e:
            self.logger.error(f"Greška pri praćenju podataka: {e}")
            return {}
            
    def shutdown(self) -> None:
        """Zaustavlja upravljanje podacima."""
        try:
            self.thread_pool.shutdown(wait=True)
            self.process_pool.shutdown(wait=True)
        except Exception as e:
            self.logger.error(f"Greška pri zatvaranju upravljanja podacima: {e}")
            gc.collect() 