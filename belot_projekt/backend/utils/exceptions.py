"""
Prilagođene iznimke za Belot aplikaciju.

Ovaj modul definira razne prilagođene iznimke koje se koriste 
u cijeloj aplikaciji za bolje upravljanje greškama.
"""

from typing import Dict, Any, Optional, List, Union
from django.utils.translation import gettext_lazy as _


class ApplicationError(Exception):
    """
    Osnovna klasa za sve prilagođene iznimke u aplikaciji.
    
    Služi kao temelj za sve ostale iznimke i definira zajedničko
    sučelje za njih.
    
    Attributes:
        message: Poruka greške
        code: Kod greške za identificiranje tipa greške
        status_code: HTTP status kod koji se vraća klijentu
        details: Dodatni detalji o grešci
    """
    
    def __init__(
        self,
        message: str = "Dogodila se greška u aplikaciji",
        code: str = "application_error",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Inicijalizacija iznimke.
        
        Args:
            message: Poruka greške
            code: Kod greške za identificiranje tipa greške
            status_code: HTTP status kod koji se vraća klijentu
            details: Dodatni detalji o grešci
        """
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Pretvara iznimku u rječnik za JSON odgovor.
        
        Returns:
            Rječnik s podacima o grešci
        """
        result = {
            'error': True,
            'message': self.message,
            'code': self.code,
            'status_code': self.status_code,
        }
        
        if self.details:
            result['details'] = self.details
        
        return result


class InvalidInputError(ApplicationError):
    """
    Iznimka za nevažeći ulazni podatak.
    
    Ova iznimka se koristi kada korisnik pošalje nevažeće
    podatke koji ne prolaze validaciju.
    """
    
    def __init__(
        self,
        message: str = "Nevažeći ulazni podaci",
        code: str = "invalid_input",
        field_errors: Optional[Dict[str, Union[str, List[str]]]] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Inicijalizacija iznimke.
        
        Args:
            message: Poruka greške
            code: Kod greške
            field_errors: Rječnik grešaka po poljima
            details: Dodatni detalji o grešci
        """
        status_code = 400  # Bad Request
        
        # Dodaj field_errors u details ako postoje
        all_details = details or {}
        if field_errors:
            all_details['field_errors'] = field_errors
        
        super().__init__(message, code, status_code, all_details)


class ResourceNotFoundError(ApplicationError):
    """
    Iznimka za resurs koji nije pronađen.
    
    Ova iznimka se koristi kada zatraženi resurs ne postoji
    u sustavu.
    """
    
    def __init__(
        self,
        message: str = "Zatraženi resurs nije pronađen",
        code: str = "resource_not_found",
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Inicijalizacija iznimke.
        
        Args:
            message: Poruka greške
            code: Kod greške
            resource_type: Tip resursa koji nije pronađen
            resource_id: ID resursa koji nije pronađen
            details: Dodatni detalji o grešci
        """
        status_code = 404  # Not Found
        
        # Dodaj resource_type i resource_id u details ako postoje
        all_details = details or {}
        if resource_type:
            all_details['resource_type'] = resource_type
        if resource_id:
            all_details['resource_id'] = resource_id
        
        super().__init__(message, code, status_code, all_details)


class AuthenticationError(ApplicationError):
    """
    Iznimka za probleme s autentikacijom.
    
    Ova iznimka se koristi kada korisnik nije pravilno autentificiran
    ili kada autentikacijski podaci nisu važeći.
    """
    
    def __init__(
        self,
        message: str = "Greška prilikom autentikacije",
        code: str = "authentication_error",
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Inicijalizacija iznimke.
        
        Args:
            message: Poruka greške
            code: Kod greške
            details: Dodatni detalji o grešci
        """
        status_code = 401  # Unauthorized
        super().__init__(message, code, status_code, details)


class PermissionDeniedError(ApplicationError):
    """
    Iznimka za nedostatak potrebnih dozvola.
    
    Ova iznimka se koristi kada korisnik nema potrebne dozvole
    za pristup resursu ili izvršavanje operacije.
    """
    
    def __init__(
        self,
        message: str = "Nemate dozvolu za pristup ovom resursu",
        code: str = "permission_denied",
        required_permission: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Inicijalizacija iznimke.
        
        Args:
            message: Poruka greške
            code: Kod greške
            required_permission: Potrebna dozvola
            details: Dodatni detalji o grešci
        """
        status_code = 403  # Forbidden
        
        # Dodaj required_permission u details ako postoji
        all_details = details or {}
        if required_permission:
            all_details['required_permission'] = required_permission
        
        super().__init__(message, code, status_code, all_details)


class ValidationError(ApplicationError):
    """
    Iznimka za greške prilikom validacije.
    
    Ova iznimka se koristi kada podaci ne prolaze validaciju,
    ali su sintaktički ispravni (za razliku od InvalidInputError).
    """
    
    def __init__(
        self,
        message: str = "Podaci nisu prošli validaciju",
        code: str = "validation_error",
        validation_errors: Optional[Dict[str, Union[str, List[str]]]] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Inicijalizacija iznimke.
        
        Args:
            message: Poruka greške
            code: Kod greške
            validation_errors: Rječnik grešaka validacije po poljima
            details: Dodatni detalji o grešci
        """
        status_code = 422  # Unprocessable Entity
        
        # Dodaj validation_errors u details ako postoje
        all_details = details or {}
        if validation_errors:
            all_details['validation_errors'] = validation_errors
        
        super().__init__(message, code, status_code, all_details)


class BusinessLogicError(ApplicationError):
    """
    Iznimka za greške u poslovnoj logici.
    
    Ova iznimka se koristi kada operacija nije moguća zbog
    pravila poslovne logike, iako su ulazni podaci validni.
    """
    
    def __init__(
        self,
        message: str = "Operacija nije moguća zbog pravila poslovne logike",
        code: str = "business_logic_error",
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Inicijalizacija iznimke.
        
        Args:
            message: Poruka greške
            code: Kod greške
            details: Dodatni detalji o grešci
        """
        status_code = 409  # Conflict
        super().__init__(message, code, status_code, details)


class ServiceUnavailableError(ApplicationError):
    """
    Iznimka za nedostupnost servisa.
    
    Ova iznimka se koristi kada vanjski servis ili komponenta
    nije dostupna ili ne radi ispravno.
    """
    
    def __init__(
        self,
        message: str = "Servis trenutno nije dostupan",
        code: str = "service_unavailable",
        service_name: Optional[str] = None,
        retry_after: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Inicijalizacija iznimke.
        
        Args:
            message: Poruka greške
            code: Kod greške
            service_name: Ime nedostupnog servisa
            retry_after: Preporučeno vrijeme (u sekundama) prije ponovnog pokušaja
            details: Dodatni detalji o grešci
        """
        status_code = 503  # Service Unavailable
        
        # Dodaj service_name i retry_after u details ako postoje
        all_details = details or {}
        if service_name:
            all_details['service_name'] = service_name
        if retry_after:
            all_details['retry_after'] = retry_after
        
        super().__init__(message, code, status_code, all_details)


class RateLimitExceededError(ApplicationError):
    """
    Iznimka za prekoračenje ograničenja broja zahtjeva.
    
    Ova iznimka se koristi kada korisnik prekorači dozvoljeni
    broj zahtjeva u određenom vremenskom periodu.
    """
    
    def __init__(
        self,
        message: str = "Prekoračili ste dozvoljeni broj zahtjeva",
        code: str = "rate_limit_exceeded",
        retry_after: Optional[int] = None,
        limit: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Inicijalizacija iznimke.
        
        Args:
            message: Poruka greške
            code: Kod greške
            retry_after: Preporučeno vrijeme (u sekundama) prije ponovnog pokušaja
            limit: Dozvoljeni broj zahtjeva
            details: Dodatni detalji o grešci
        """
        status_code = 429  # Too Many Requests
        
        # Dodaj retry_after i limit u details ako postoje
        all_details = details or {}
        if retry_after:
            all_details['retry_after'] = retry_after
        if limit:
            all_details['limit'] = limit
        
        super().__init__(message, code, status_code, all_details)


class InvalidStateError(ApplicationError):
    """
    Iznimka za nevažeće stanje.
    
    Ova iznimka se koristi kada je operacija zatražena na resursu
    koji je u stanju koje ne dopušta tu operaciju.
    """
    
    def __init__(
        self,
        message: str = "Operacija nije dozvoljena u trenutnom stanju",
        code: str = "invalid_state",
        current_state: Optional[str] = None,
        allowed_states: Optional[List[str]] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Inicijalizacija iznimke.
        
        Args:
            message: Poruka greške
            code: Kod greške
            current_state: Trenutno stanje resursa
            allowed_states: Dozvoljena stanja za operaciju
            details: Dodatni detalji o grešci
        """
        status_code = 409  # Conflict
        
        # Dodaj current_state i allowed_states u details ako postoje
        all_details = details or {}
        if current_state:
            all_details['current_state'] = current_state
        if allowed_states:
            all_details['allowed_states'] = allowed_states
        
        super().__init__(message, code, status_code, all_details)