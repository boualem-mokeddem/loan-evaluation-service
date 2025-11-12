# -*- coding: utf-8 -*-
from spyne import (Application, rpc, ServiceBase, Unicode, Decimal, Boolean, 
                   Integer, ComplexModel, DateTime)
from spyne.protocol.soap import Soap11
from spyne.server.wsgi import WsgiApplication
from spyne.model.fault import Fault
import logging
import re
from datetime import datetime
from decimal import Decimal as PyDecimal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ClientIdentity(ComplexModel):
    __namespace__ = "urn:solvency.verification.service:v1"
    client_id = Unicode(min_occurs=1)
    name = Unicode(min_occurs=1)
    address = Unicode(min_occurs=1)
    email = Unicode(min_occurs=1)


class Financials(ComplexModel):
    __namespace__ = "urn:solvency.verification.service:v1"
    monthly_income = Decimal(min_occurs=1)
    monthly_expenses = Decimal(min_occurs=1)


class CreditHistory(ComplexModel):
    __namespace__ = "urn:solvency.verification.service:v1"
    debt = Decimal(min_occurs=1)
    late_payments = Integer(min_occurs=1)
    has_bankruptcy = Boolean(min_occurs=1)


class RequestStatus(ComplexModel):
    __namespace__ = "urn:solvency.verification.service:v1"
    correlation_id = Unicode(min_occurs=1)
    status = Unicode(min_occurs=1)
    message = Unicode(min_occurs=1)


# ============ BASE DE DONNÉES EN MÉMOIRE ============

CLIENTS_DB = {
    "client-001": {
        "identity": {
            "name": "John Doe",
            "address": "123 Main St, Boston MA",
            "email": "john.doe@example.com"
        },
        "financials": {"monthly_income": PyDecimal("4000"), "monthly_expenses": PyDecimal("3000")},
        "credit": {"debt": PyDecimal("5000"), "late_payments": 2, "has_bankruptcy": False}
    },
    "client-002": {
        "identity": {
            "name": "Alice Smith",
            "address": "456 Elm St, NYC",
            "email": "alice.smith@example.com"
        },
        "financials": {"monthly_income": PyDecimal("5500"), "monthly_expenses": PyDecimal("2500")},
        "credit": {"debt": PyDecimal("2000"), "late_payments": 0, "has_bankruptcy": False}
    },
    "client-003": {
        "identity": {
            "name": "Bob Johnson",
            "address": "789 Oak St, LA",
            "email": "bob.johnson@example.com"
        },
        "financials": {"monthly_income": PyDecimal("3500"), "monthly_expenses": PyDecimal("3200")},
        "credit": {"debt": PyDecimal("15000"), "late_payments": 5, "has_bankruptcy": True}
    },
    "client-004": {
        "identity": {
            "name": "Sarah Harrouche",
            "address": "UVSQ",
            "email": "sarahharrouche2004@gmail.com"
        },
        "financials": {"monthly_income": PyDecimal("4500"), "monthly_expenses": PyDecimal("2500")},
        "credit": {"debt": PyDecimal("1000"), "late_payments": 1, "has_bankruptcy": True}
    }

}

LOAN_REQUESTS_DB = {}


# ============ SERVICES CRUD ============

class ClientDirectoryService(ServiceBase):
    @rpc(Unicode, _returns=ClientIdentity)
    def get_client_identity(ctx, client_id):
        logger.info(f"[CRUD] GetClientIdentity({client_id})")
        
        if not _validate_client_id(client_id):
            raise Fault("Client.ValidationError", 
                       f"Format clientId invalide. Attendu: client-XXX")
        
        if client_id not in CLIENTS_DB:
            raise Fault("Client.NotFound", 
                       f"Client '{client_id}' non trouvé dans le système.")
        
        data = CLIENTS_DB[client_id]["identity"]
        logger.info(f"[CRUD] ✓ Client trouvé: {data['name']}")
        
        return ClientIdentity(
            client_id=client_id,
            name=data["name"],
            address=data["address"],
            email=data["email"]
        )


class FinancialDataService(ServiceBase):
    @rpc(Unicode, _returns=Financials)
    def get_client_financials(ctx, client_id):
        logger.info(f"[CRUD] GetClientFinancials({client_id})")
        
        if not _validate_client_id(client_id):
            raise Fault("Client.ValidationError", f"Format clientId invalide")
        
        if client_id not in CLIENTS_DB:
            raise Fault("Client.NotFound", f"Client '{client_id}' non trouvé.")
        
        data = CLIENTS_DB[client_id]["financials"]
        logger.info(f"[CRUD] ✓ Revenus: ${data['monthly_income']}, "
                   f"Dépenses: ${data['monthly_expenses']}")
        
        return Financials(
            monthly_income=data["monthly_income"], 
            monthly_expenses=data["monthly_expenses"]
        )


class CreditBureauService(ServiceBase):
    @rpc(Unicode, _returns=CreditHistory)
    def get_client_credit_history(ctx, client_id):
        logger.info(f"[CRUD] GetClientCreditHistory({client_id})")
        
        if not _validate_client_id(client_id):
            raise Fault("Client.ValidationError", f"Format clientId invalide")
        
        if client_id not in CLIENTS_DB:
            raise Fault("Client.NotFound", f"Client '{client_id}' non trouvé.")
        
        data = CLIENTS_DB[client_id]["credit"]
        logger.info(f"[CRUD] ✓ Dettes: ${data['debt']}, "
                   f"Retards: {data['late_payments']}")
        
        return CreditHistory(
            debt=data["debt"], 
            late_payments=data["late_payments"], 
            has_bankruptcy=data["has_bankruptcy"]
        )


class DataAccessService(ServiceBase):
    """Service d'accès aux données (lecture seule)"""
    
    @rpc(Unicode, Unicode, _returns=RequestStatus)
    def save_loan_request(ctx, correlation_id, request_json):
        """Sauvegarde une demande de prêt"""
        logger.info(f"[CRUD] SaveLoanRequest({correlation_id})")
        
        import json
        try:
            request_data = json.loads(request_json) if isinstance(request_json, str) else request_json
            LOAN_REQUESTS_DB[correlation_id] = {
                "correlation_id": correlation_id,
                "status": "REÇUE",
                "created_at": datetime.utcnow().isoformat(),
                "data": request_data
            }
            logger.info(f"[CRUD] ✓ Demande sauvegardée")
            
            return RequestStatus(
                correlation_id=correlation_id,
                status="REÇUE",
                message=f"Demande {correlation_id} sauvegardée"
            )
        except Exception as e:
            logger.error(f"[CRUD] ✗ Erreur: {str(e)}")
            raise Fault("Server.StorageError", str(e))
    
    @rpc(Unicode, Unicode, _returns=RequestStatus)
    def update_request_status(ctx, correlation_id, status):
        """Mise à jour du statut de demande"""
        logger.info(f"[CRUD] UpdateStatus({correlation_id}) -> {status}")
        
        if correlation_id not in LOAN_REQUESTS_DB:
            raise Fault("Request.NotFound", f"Demande {correlation_id} non trouvée.")
        
        LOAN_REQUESTS_DB[correlation_id]["status"] = status
        LOAN_REQUESTS_DB[correlation_id]["updated_at"] = datetime.utcnow().isoformat()
        
        logger.info(f"[CRUD] ✓ Statut mis à jour: {status}")
        
        return RequestStatus(
            correlation_id=correlation_id,
            status=status,
            message=f"Statut mis à jour: {status}"
        )


def _validate_client_id(client_id):
    """Valide le format du clientId: client-XXX"""
    return bool(re.match(r"^client-\d{3}$", client_id))


application = Application(
    [ClientDirectoryService, FinancialDataService, CreditBureauService, DataAccessService],
    tns='urn:solvency.verification.crud:v1',
    in_protocol=Soap11(validator='lxml'),
    out_protocol=Soap11()
)

wsgi_application = WsgiApplication(application)

if __name__ == '__main__':
    from wsgiref.simple_server import make_server
    logger.info("[CRUD] 🚀 Démarrage sur :5002")
    server = make_server('0.0.0.0', 5002, wsgi_application)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("[CRUD] 🛑 Arrêt")
