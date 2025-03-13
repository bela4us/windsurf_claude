"""
Middleware za podršku CORS (Cross-Origin Resource Sharing) u Belot aplikaciji.

Ovaj modul implementira middleware koji upravlja CORS zaglavljima, omogućujući
pristup API-ju s različitih domena. To je ključno za omogućavanje frontend
aplikacijama koje se nalaze na različitim domenama da komuniciraju s API-jem.
"""

from django.utils.deprecation import MiddlewareMixin
from django.conf import settings


class CORSMiddleware(MiddlewareMixin):
    """
    Middleware za upravljanje CORS zaglavljima.
    
    Dodaje potrebna CORS zaglavlja u odgovore kako bi omogućio pristup
    API-ju s različitih domena.
    """
    
    def __init__(self, get_response):
        """Inicijalizira middleware s funkcijom get_response."""
        self.get_response = get_response
        
        # Učitaj postavke iz settings.py ako postoje
        self.cors_origin = getattr(settings, 'CORS_ALLOW_ORIGIN', '*')
        self.cors_methods = getattr(settings, 'CORS_ALLOW_METHODS', 'GET, POST, PUT, PATCH, DELETE, OPTIONS')
        self.cors_headers = getattr(settings, 'CORS_ALLOW_HEADERS', 'Content-Type, Authorization, X-Requested-With')
        self.cors_credentials = getattr(settings, 'CORS_ALLOW_CREDENTIALS', 'true')
        self.cors_max_age = getattr(settings, 'CORS_MAX_AGE', 86400)  # 24 sata
        
        # Lista dozvoljenih domena (ako nije *)
        self.allowed_origins = getattr(settings, 'CORS_ALLOWED_ORIGINS', [])
        if self.cors_origin != '*' and isinstance(self.allowed_origins, list):
            self.use_allowed_origins = True
        else:
            self.use_allowed_origins = False
    
    def __call__(self, request):
        """
        Obrađuje zahtjev i dodaje CORS zaglavlja u odgovor.
        
        Args:
            request: HTTP zahtjev
            
        Returns:
            HttpResponse: Odgovor na zahtjev
        """
        # Spremi Origin zaglavlje za kasnije korištenje
        origin = request.META.get('HTTP_ORIGIN')
        
        # Obradi zahtjev
        response = self.get_response(request)
        
        # Dodaj CORS zaglavlja
        if origin:
            # Provjeri je li domena dozvoljena
            if self.use_allowed_origins:
                if origin in self.allowed_origins:
                    response['Access-Control-Allow-Origin'] = origin
            else:
                response['Access-Control-Allow-Origin'] = self.cors_origin
            
            # Ako koristimo '*' za dozvoljene origine, ne možemo koristiti credentials
            if self.cors_origin != '*':
                response['Access-Control-Allow-Credentials'] = self.cors_credentials
            
            response['Access-Control-Allow-Methods'] = self.cors_methods
            response['Access-Control-Allow-Headers'] = self.cors_headers
            response['Access-Control-Max-Age'] = str(self.cors_max_age)
        
        # Za OPTIONS zahtjeve (preflight), vrati prazan odgovor s odgovarajućim zaglavljima
        if request.method == 'OPTIONS':
            response['Content-Length'] = '0'
            response.status_code = 200
        
        return response


class SameSiteMiddleware(MiddlewareMixin):
    """
    Middleware za upravljanje SameSite atributom kolačića.
    
    SameSite atribut određuje kako se kolačići šalju u zahtjevima koji dolaze s 
    drugih domena, što je važno za sigurnost web aplikacija, posebno za zaštitu
    od CSRF napada.
    """
    
    def __init__(self, get_response):
        """Inicijalizira middleware s funkcijom get_response."""
        self.get_response = get_response
        
        # Učitaj postavke iz settings.py ako postoje
        self.samesite_value = getattr(settings, 'SESSION_COOKIE_SAMESITE', 'Lax')
        
        # Za različite okoline, različiti SameSite
        self.debug_samesite = getattr(settings, 'DEBUG_COOKIE_SAMESITE', 'None')
        
        # Za razvoj, koristimo 'None' da bismo mogli testirati frontend koji nije na istoj domeni
        self.use_debug_samesite = settings.DEBUG
    
    def __call__(self, request):
        """
        Obrađuje zahtjev i postavlja SameSite atribut u kolačićima.
        
        Args:
            request: HTTP zahtjev
            
        Returns:
            HttpResponse: Odgovor na zahtjev
        """
        # Obradi zahtjev
        response = self.get_response(request)
        
        # Postavi SameSite atribut u Set-Cookie zaglavljima
        if 'Set-Cookie' in response:
            cookies = response.get('Set-Cookie').split(',')
            result_cookies = []
            
            for cookie in cookies:
                # Ako je u debug modu, koristi debug_samesite
                samesite = self.debug_samesite if self.use_debug_samesite else self.samesite_value
                
                # Ako je SameSite='None', moramo postaviti i Secure
                if samesite == 'None':
                    if 'SameSite=' not in cookie:
                        cookie += f'; SameSite={samesite}; Secure'
                    else:
                        cookie = cookie.replace('SameSite=Lax', f'SameSite={samesite}; Secure')
                        cookie = cookie.replace('SameSite=Strict', f'SameSite={samesite}; Secure')
                else:
                    if 'SameSite=' not in cookie:
                        cookie += f'; SameSite={samesite}'
                    else:
                        cookie = cookie.replace('SameSite=None; Secure', f'SameSite={samesite}')
                        cookie = cookie.replace('SameSite=None', f'SameSite={samesite}')
                
                result_cookies.append(cookie)
            
            response['Set-Cookie'] = ','.join(result_cookies)
        
        return response