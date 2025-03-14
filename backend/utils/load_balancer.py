from django.core.cache import cache
from django.conf import settings
from typing import Dict, Any, List, Optional
import logging
import time
import json
from functools import wraps
import psutil
import requests
from django.http import HttpResponse
import socket

logger = logging.getLogger(__name__)

class LoadBalancer:
    def __init__(self):
        self.health_check_interval = 30  # sekunde
        self.health_check_timeout = 5
        self.max_failures = 3
        self.backend_servers = []
        self.server_health = {}
        self.session_affinity = {}
        self.least_connections = {}

    def add_backend_server(self, host: str, port: int, weight: int = 1):
        """Dodaj backend server"""
        server = {
            'host': host,
            'port': port,
            'weight': weight,
            'failures': 0,
            'last_check': 0
        }
        self.backend_servers.append(server)
        self.server_health[host] = True
        self.least_connections[host] = 0
        logger.info(f"Dodan backend server: {host}:{port}")

    def remove_backend_server(self, host: str):
        """Ukloni backend server"""
        self.backend_servers = [s for s in self.backend_servers if s['host'] != host]
        self.server_health.pop(host, None)
        self.least_connections.pop(host, None)
        logger.info(f"Uklonjen backend server: {host}")

    def health_check(self):
        """Provjeri zdravlje backend servera"""
        current_time = time.time()
        
        for server in self.backend_servers:
            if current_time - server['last_check'] < self.health_check_interval:
                continue
                
            try:
                response = requests.get(
                    f"http://{server['host']}:{server['port']}/health",
                    timeout=self.health_check_timeout
                )
                
                if response.status_code == 200:
                    self.server_health[server['host']] = True
                    server['failures'] = 0
                else:
                    self._handle_server_failure(server)
                    
            except Exception as e:
                logger.error(f"Health check greška za {server['host']}: {e}")
                self._handle_server_failure(server)
                
            server['last_check'] = current_time

    def _handle_server_failure(self, server: Dict[str, Any]):
        """Upravljanje greškama servera"""
        server['failures'] += 1
        self.server_health[server['host']] = False
        
        if server['failures'] >= self.max_failures:
            logger.warning(f"Server {server['host']} je označen kao nezdrav")
            self.remove_backend_server(server['host'])

    def get_healthy_servers(self) -> List[Dict[str, Any]]:
        """Dohvati zdrave servere"""
        return [
            server for server in self.backend_servers
            if self.server_health.get(server['host'], False)
        ]

    def get_next_server(self, session_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Dohvati sljedeći server prema strategiji"""
        healthy_servers = self.get_healthy_servers()
        if not healthy_servers:
            return None
            
        # Session affinity
        if session_id and session_id in self.session_affinity:
            server = self.session_affinity[session_id]
            if server in healthy_servers:
                return server
                
        # Least connections
        server = min(
            healthy_servers,
            key=lambda s: self.least_connections[s['host']]
        )
        
        # Ažuriraj broj konekcija
        self.least_connections[server['host']] += 1
        
        # Spremi session affinity
        if session_id:
            self.session_affinity[session_id] = server
            
        return server

    def release_connection(self, server: Dict[str, Any]):
        """Oslobodi konekciju"""
        self.least_connections[server['host']] = max(
            0,
            self.least_connections[server['host']] - 1
        )

    def remove_session_affinity(self, session_id: str):
        """Ukloni session affinity"""
        if session_id in self.session_affinity:
            server = self.session_affinity[session_id]
            self.release_connection(server)
            del self.session_affinity[session_id]

    def get_server_stats(self) -> Dict[str, Any]:
        """Dohvati statistiku servera"""
        return {
            'total_servers': len(self.backend_servers),
            'healthy_servers': len(self.get_healthy_servers()),
            'server_health': self.server_health,
            'least_connections': self.least_connections,
            'session_affinity': len(self.session_affinity)
        }

    def auto_scale(self):
        """Auto-scaling logika"""
        try:
            # Provjeri CPU i memoriju
            cpu_percent = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            
            # Ako je opterećenje previsoko, dodaj server
            if cpu_percent > 80 or memory.percent > 80:
                self._add_server()
                
            # Ako je opterećenje prenisko, ukloni server
            elif cpu_percent < 20 and memory.percent < 20:
                self._remove_server()
                
        except Exception as e:
            logger.error(f"Greška pri auto-scalingu: {e}")

    def _add_server(self):
        """Dodaj novi server"""
        # Implementacija ovisi o cloud provideru
        # Primjer za AWS:
        # ec2.run_instances(...)
        pass

    def _remove_server(self):
        """Ukloni server"""
        # Implementacija ovisi o cloud provideru
        # Primjer za AWS:
        # ec2.terminate_instances(...)
        pass

# Inicijalizacija load balancera
load_balancer = LoadBalancer() 