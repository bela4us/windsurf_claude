<<<<<<< HEAD
from typing import Dict, Any, Optional, List, Callable, Union
import sqlalchemy
from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import QueuePool
import threading
from datetime import datetime
from dataclasses import dataclass
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
from pathlib import Path
import json
import time
from contextlib import contextmanager
import psycopg2
import aiomysql
import aioredis
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

@dataclass
class DatabaseStats:
    total_queries: int = 0
    slow_queries: int = 0
    avg_query_time: float = 0.0
    active_connections: int = 0
    pool_size: int = 0
    overflow: int = 0
    last_optimization: Optional[datetime] = None

class DatabaseManager:
    def __init__(
        self,
        db_url: str,
        pool_size: int = 5,
        max_overflow: int = 10,
        pool_timeout: int = 30,
        pool_recycle: int = 1800,
        slow_query_threshold: float = 1.0
    ):
        self.logger = logging.getLogger(__name__)
        self.db_url = db_url
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.pool_timeout = pool_timeout
        self.pool_recycle = pool_recycle
        self.slow_query_threshold = slow_query_threshold
        
        self.engine = self._create_engine()
        self.Session = scoped_session(sessionmaker(bind=self.engine))
        self.stats = DatabaseStats()
        self._lock = threading.Lock()
        
        self._start_optimization_task()
        
    def _create_engine(self) -> sqlalchemy.engine.Engine:
        """Kreira SQLAlchemy engine s optimizacijama."""
        return create_engine(
            self.db_url,
            poolclass=QueuePool,
            pool_size=self.pool_size,
            max_overflow=self.max_overflow,
            pool_timeout=self.pool_timeout,
            pool_recycle=self.pool_recycle,
            pool_pre_ping=True,
            echo=False
        )
        
    def _start_optimization_task(self) -> None:
        """Započinje periodičnu optimizaciju baze."""
        def optimize():
            while True:
                try:
                    self._optimize_database()
                    time.sleep(3600)  # Svaki sat
                except Exception as e:
                    self.logger.error(f"Greška pri optimizaciji baze: {e}")
                    
        thread = threading.Thread(target=optimize, daemon=True)
        thread.start()
        
    def _optimize_database(self) -> None:
        """Optimizira bazu podataka."""
        try:
            with self.engine.connect() as conn:
                # Analiziraj tablice
                conn.execute("ANALYZE")
                
                # Vakumiraj tablice
                conn.execute("VACUUM")
                
                # Reindeksiraj tablice
                conn.execute("REINDEX DATABASE")
                
            self.stats.last_optimization = datetime.now()
            
        except Exception as e:
            self.logger.error(f"Greška pri optimizaciji baze: {e}")
            
    @contextmanager
    def get_session(self):
        """Kontekstni menadžer za dohvat sesije."""
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
            
    def execute_query(
        self,
        query: str,
        params: Optional[tuple] = None
    ) -> List[Dict[str, Any]]:
        """Izvršava SQL upit s praćenjem performansi."""
        try:
            start_time = time.time()
            
            with self.get_session() as session:
                result = session.execute(query, params or ())
                rows = [dict(row) for row in result]
                
            query_time = time.time() - start_time
            
            with self._lock:
                self.stats.total_queries += 1
                if query_time > self.slow_query_threshold:
                    self.stats.slow_queries += 1
                self.stats.avg_query_time = (
                    (self.stats.avg_query_time * (self.stats.total_queries - 1) + query_time) /
                    self.stats.total_queries
                )
                
            return rows
            
        except Exception as e:
            self.logger.error(f"Greška pri izvršavanju upita: {e}")
            raise
            
    def execute_many(
        self,
        query: str,
        params: List[tuple]
    ) -> None:
        """Izvršava više SQL upita."""
        try:
            with self.get_session() as session:
                session.execute(query, params)
                
        except Exception as e:
            self.logger.error(f"Greška pri izvršavanju više upita: {e}")
            raise
            
    def bulk_insert(
        self,
        table: str,
        data: List[Dict[str, Any]]
    ) -> None:
        """Izvršava bulk insert."""
        try:
            with self.get_session() as session:
                session.bulk_insert_mappings(table, data)
                
        except Exception as e:
            self.logger.error(f"Greška pri bulk insertu: {e}")
            raise
            
    def bulk_update(
        self,
        table: str,
        data: List[Dict[str, Any]]
    ) -> None:
        """Izvršava bulk update."""
        try:
            with self.get_session() as session:
                session.bulk_update_mappings(table, data)
                
        except Exception as e:
            self.logger.error(f"Greška pri bulk updateu: {e}")
            raise
            
    def bulk_delete(
        self,
        table: str,
        ids: List[Any]
    ) -> None:
        """Izvršava bulk delete."""
        try:
            with self.get_session() as session:
                session.query(table).filter(table.id.in_(ids)).delete()
                
        except Exception as e:
            self.logger.error(f"Greška pri bulk deleteu: {e}")
            raise
            
    def create_index(
        self,
        table: str,
        columns: List[str],
        unique: bool = False
    ) -> None:
        """Kreira indeks na tablici."""
        try:
            with self.get_session() as session:
                index_name = f"idx_{table}_{'_'.join(columns)}"
                session.execute(
                    f"CREATE {'UNIQUE' if unique else ''} INDEX {index_name} "
                    f"ON {table} ({', '.join(columns)})"
                )
                
        except Exception as e:
            self.logger.error(f"Greška pri kreiranju indeksa: {e}")
            raise
            
    def drop_index(
        self,
        table: str,
        columns: List[str]
    ) -> None:
        """Briše indeks s tablice."""
        try:
            with self.get_session() as session:
                index_name = f"idx_{table}_{'_'.join(columns)}"
                session.execute(f"DROP INDEX {index_name}")
                
        except Exception as e:
            self.logger.error(f"Greška pri brisanju indeksa: {e}")
            raise
            
    def analyze_table(self, table: str) -> None:
        """Analizira tablicu."""
        try:
            with self.get_session() as session:
                session.execute(f"ANALYZE {table}")
                
        except Exception as e:
            self.logger.error(f"Greška pri analizi tablice: {e}")
            raise
            
    def vacuum_table(self, table: str) -> None:
        """Vakumira tablicu."""
        try:
            with self.get_session() as session:
                session.execute(f"VACUUM {table}")
                
        except Exception as e:
            self.logger.error(f"Greška pri vakumiranju tablice: {e}")
            raise
            
    def reindex_table(self, table: str) -> None:
        """Reindeksira tablicu."""
        try:
            with self.get_session() as session:
                session.execute(f"REINDEX TABLE {table}")
                
        except Exception as e:
            self.logger.error(f"Greška pri reindeksiranju tablice: {e}")
            raise
            
    def get_stats(self) -> DatabaseStats:
        """Dohvaća statistiku baze."""
        try:
            with self.engine.connect() as conn:
                self.stats.active_connections = conn.execute(
                    "SELECT count(*) FROM pg_stat_activity"
                ).scalar()
                
            return self.stats
            
        except Exception as e:
            self.logger.error(f"Greška pri dohvatu statistike baze: {e}")
            return self.stats
            
    def shutdown(self) -> None:
        """Zaustavlja upravljanje bazom."""
        try:
            self.Session.remove()
            self.engine.dispose()
        except Exception as e:
=======
from typing import Dict, Any, Optional, List, Callable, Union
import sqlalchemy
from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import QueuePool
import threading
from datetime import datetime
from dataclasses import dataclass
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
from pathlib import Path
import json
import time
from contextlib import contextmanager
import psycopg2
import aiomysql
import aioredis
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

@dataclass
class DatabaseStats:
    total_queries: int = 0
    slow_queries: int = 0
    avg_query_time: float = 0.0
    active_connections: int = 0
    pool_size: int = 0
    overflow: int = 0
    last_optimization: Optional[datetime] = None

class DatabaseManager:
    def __init__(
        self,
        db_url: str,
        pool_size: int = 5,
        max_overflow: int = 10,
        pool_timeout: int = 30,
        pool_recycle: int = 1800,
        slow_query_threshold: float = 1.0
    ):
        self.logger = logging.getLogger(__name__)
        self.db_url = db_url
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.pool_timeout = pool_timeout
        self.pool_recycle = pool_recycle
        self.slow_query_threshold = slow_query_threshold
        
        self.engine = self._create_engine()
        self.Session = scoped_session(sessionmaker(bind=self.engine))
        self.stats = DatabaseStats()
        self._lock = threading.Lock()
        
        self._start_optimization_task()
        
    def _create_engine(self) -> sqlalchemy.engine.Engine:
        """Kreira SQLAlchemy engine s optimizacijama."""
        return create_engine(
            self.db_url,
            poolclass=QueuePool,
            pool_size=self.pool_size,
            max_overflow=self.max_overflow,
            pool_timeout=self.pool_timeout,
            pool_recycle=self.pool_recycle,
            pool_pre_ping=True,
            echo=False
        )
        
    def _start_optimization_task(self) -> None:
        """Započinje periodičnu optimizaciju baze."""
        def optimize():
            while True:
                try:
                    self._optimize_database()
                    time.sleep(3600)  # Svaki sat
                except Exception as e:
                    self.logger.error(f"Greška pri optimizaciji baze: {e}")
                    
        thread = threading.Thread(target=optimize, daemon=True)
        thread.start()
        
    def _optimize_database(self) -> None:
        """Optimizira bazu podataka."""
        try:
            with self.engine.connect() as conn:
                # Analiziraj tablice
                conn.execute("ANALYZE")
                
                # Vakumiraj tablice
                conn.execute("VACUUM")
                
                # Reindeksiraj tablice
                conn.execute("REINDEX DATABASE")
                
            self.stats.last_optimization = datetime.now()
            
        except Exception as e:
            self.logger.error(f"Greška pri optimizaciji baze: {e}")
            
    @contextmanager
    def get_session(self):
        """Kontekstni menadžer za dohvat sesije."""
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
            
    def execute_query(
        self,
        query: str,
        params: Optional[tuple] = None
    ) -> List[Dict[str, Any]]:
        """Izvršava SQL upit s praćenjem performansi."""
        try:
            start_time = time.time()
            
            with self.get_session() as session:
                result = session.execute(query, params or ())
                rows = [dict(row) for row in result]
                
            query_time = time.time() - start_time
            
            with self._lock:
                self.stats.total_queries += 1
                if query_time > self.slow_query_threshold:
                    self.stats.slow_queries += 1
                self.stats.avg_query_time = (
                    (self.stats.avg_query_time * (self.stats.total_queries - 1) + query_time) /
                    self.stats.total_queries
                )
                
            return rows
            
        except Exception as e:
            self.logger.error(f"Greška pri izvršavanju upita: {e}")
            raise
            
    def execute_many(
        self,
        query: str,
        params: List[tuple]
    ) -> None:
        """Izvršava više SQL upita."""
        try:
            with self.get_session() as session:
                session.execute(query, params)
                
        except Exception as e:
            self.logger.error(f"Greška pri izvršavanju više upita: {e}")
            raise
            
    def bulk_insert(
        self,
        table: str,
        data: List[Dict[str, Any]]
    ) -> None:
        """Izvršava bulk insert."""
        try:
            with self.get_session() as session:
                session.bulk_insert_mappings(table, data)
                
        except Exception as e:
            self.logger.error(f"Greška pri bulk insertu: {e}")
            raise
            
    def bulk_update(
        self,
        table: str,
        data: List[Dict[str, Any]]
    ) -> None:
        """Izvršava bulk update."""
        try:
            with self.get_session() as session:
                session.bulk_update_mappings(table, data)
                
        except Exception as e:
            self.logger.error(f"Greška pri bulk updateu: {e}")
            raise
            
    def bulk_delete(
        self,
        table: str,
        ids: List[Any]
    ) -> None:
        """Izvršava bulk delete."""
        try:
            with self.get_session() as session:
                session.query(table).filter(table.id.in_(ids)).delete()
                
        except Exception as e:
            self.logger.error(f"Greška pri bulk deleteu: {e}")
            raise
            
    def create_index(
        self,
        table: str,
        columns: List[str],
        unique: bool = False
    ) -> None:
        """Kreira indeks na tablici."""
        try:
            with self.get_session() as session:
                index_name = f"idx_{table}_{'_'.join(columns)}"
                session.execute(
                    f"CREATE {'UNIQUE' if unique else ''} INDEX {index_name} "
                    f"ON {table} ({', '.join(columns)})"
                )
                
        except Exception as e:
            self.logger.error(f"Greška pri kreiranju indeksa: {e}")
            raise
            
    def drop_index(
        self,
        table: str,
        columns: List[str]
    ) -> None:
        """Briše indeks s tablice."""
        try:
            with self.get_session() as session:
                index_name = f"idx_{table}_{'_'.join(columns)}"
                session.execute(f"DROP INDEX {index_name}")
                
        except Exception as e:
            self.logger.error(f"Greška pri brisanju indeksa: {e}")
            raise
            
    def analyze_table(self, table: str) -> None:
        """Analizira tablicu."""
        try:
            with self.get_session() as session:
                session.execute(f"ANALYZE {table}")
                
        except Exception as e:
            self.logger.error(f"Greška pri analizi tablice: {e}")
            raise
            
    def vacuum_table(self, table: str) -> None:
        """Vakumira tablicu."""
        try:
            with self.get_session() as session:
                session.execute(f"VACUUM {table}")
                
        except Exception as e:
            self.logger.error(f"Greška pri vakumiranju tablice: {e}")
            raise
            
    def reindex_table(self, table: str) -> None:
        """Reindeksira tablicu."""
        try:
            with self.get_session() as session:
                session.execute(f"REINDEX TABLE {table}")
                
        except Exception as e:
            self.logger.error(f"Greška pri reindeksiranju tablice: {e}")
            raise
            
    def get_stats(self) -> DatabaseStats:
        """Dohvaća statistiku baze."""
        try:
            with self.engine.connect() as conn:
                self.stats.active_connections = conn.execute(
                    "SELECT count(*) FROM pg_stat_activity"
                ).scalar()
                
            return self.stats
            
        except Exception as e:
            self.logger.error(f"Greška pri dohvatu statistike baze: {e}")
            return self.stats
            
    def shutdown(self) -> None:
        """Zaustavlja upravljanje bazom."""
        try:
            self.Session.remove()
            self.engine.dispose()
        except Exception as e:
>>>>>>> c45eb88e3e23e6f6a3bf252c5a572f1c5cdb8266
            self.logger.error(f"Greška pri zatvaranju baze: {e}") 