# -*- coding: utf-8 -*-
from spyne import (Application, rpc, ServiceBase, Unicode, Decimal, Boolean, 
                   ComplexModel, Integer)
from spyne.protocol.soap import Soap11
from spyne.server.wsgi import WsgiApplication
from spyne.model.fault import Fault
import re
import logging
from decimal import Decimal as PyDecimal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ExtractedPropertyInfo(ComplexModel):
    __namespace__ = "urn:solvency.verification.service:v1"
    client_id = Unicode(min_occurs=1)
    full_name = Unicode(min_occurs=1)
    loan_amount = Decimal(min_occurs=1)
    loan_duration = Integer(min_occurs=1)
    property_address = Unicode(min_occurs=1)
    property_description = Unicode(min_occurs=1)
    property_surface = Integer(min_occurs=1)
    construction_year = Integer(min_occurs=1)
    confidence = Decimal(min_occurs=1)


class InformationExtractionService(ServiceBase):
    """
    Service d'extraction d'information
    Format attendu: KEY: VALUE (ligne par ligne)
    FULL_NAME est optionnel, tous les autres champs sont obligatoires
    """
    
    @rpc(Unicode, Unicode, _returns=ExtractedPropertyInfo)
    def extract_property_info(ctx, client_id, request_text):
        """
        Extrait les informations structurées de la demande
        Format requis:
        CLIENT_ID: xxx
        FULL_NAME: xxx (OPTIONNEL)
        LOAN_AMOUNT: xxx
        LOAN_DURATION: xxx
        PROPERTY_ADDRESS: xxx
        PROPERTY_DESCRIPTION: xxx
        PROPERTY_SURFACE: xxx
        CONSTRUCTION_YEAR: xxxx
        """
        logger.info(f"[IE] ExtractPropertyInfo({client_id})")
        
        try:
            if not request_text or len(request_text.strip()) < 20:
                raise Fault("Property.ValidationError", 
                           "Texte de demande trop court (minimum 20 caractères)")
            
            if not re.match(r"^client-\d{3}$", client_id):
                raise Fault("Client.ValidationError", 
                           "Format clientId invalide: attendu 'client-XXX'")
            
            text_normalized = request_text.strip()
            extracted = {}
            missing = []
            
            # Extraction Full Name (OPTIONNEL)
            full_name = _extract_value(text_normalized, r"FULL_NAME\s*:\s*(.+?)(?:\n|$)")
            if full_name:
                extracted["full_name"] = full_name
                logger.info(f"[IE] ✓ Nom: {full_name}")
            else:
                extracted["full_name"] = "N/A"
                logger.info(f"[IE] ⚠ Nom non fourni (optionnel)")
            
            # Extraction Loan Amount
            loan_amount = _extract_number(text_normalized, r"LOAN_AMOUNT\s*:\s*(\d+)")
            if loan_amount > 0:
                extracted["loan_amount"] = PyDecimal(str(loan_amount))
                logger.info(f"[IE] ✓ Montant prêt: ${loan_amount:,}")
            else:
                missing.append("montant prêt")
            
            # Extraction Loan Duration
            loan_duration = _extract_number(text_normalized, r"LOAN_DURATION\s*:\s*(\d+)")
            if loan_duration > 0:
                extracted["loan_duration"] = min(loan_duration, 40)
                logger.info(f"[IE] ✓ Durée: {loan_duration} ans")
            else:
                missing.append("durée prêt")
            
            # Extraction Property Address
            property_address = _extract_value(text_normalized, r"PROPERTY_ADDRESS\s*:\s*(.+?)(?:\n|$)")
            if property_address:
                extracted["property_address"] = property_address
                logger.info(f"[IE] ✓ Adresse: {property_address}")
            else:
                missing.append("adresse propriété")
            
            # Extraction Property Description
            property_description = _extract_value(text_normalized, r"PROPERTY_DESCRIPTION\s*:\s*(.+?)(?:\n|$)")
            if property_description:
                extracted["property_description"] = property_description
                logger.info(f"[IE] ✓ Description: {property_description}")
            else:
                missing.append("description propriété")
            
            # Extraction Property Surface
            property_surface = _extract_number(text_normalized, r"PROPERTY_SURFACE\s*:\s*(\d+)")
            if property_surface > 0:
                extracted["property_surface"] = property_surface
                logger.info(f"[IE] ✓ Surface: {property_surface} m²")
            else:
                missing.append("surface propriété")
            
            # Extraction Construction Year
            construction_year = _extract_number(text_normalized, r"CONSTRUCTION_YEAR\s*:\s*(\d{4})")
            if construction_year > 0:
                extracted["construction_year"] = construction_year
                logger.info(f"[IE] ✓ Année: {construction_year}")
            else:
                missing.append("année construction")
            
            if missing:
                missing_str = ", ".join(missing)
                error_msg = (f"Champs manquants : {missing_str}. "
                           f"Veuillez fournir tous les champs au format requis.")
                logger.error(f"[IE] ✗ Manquants: {missing_str}")
                raise Fault("Property.IncompleteData", error_msg)
            
            logger.info(f"[IE] ✅ Extraction complète")
            
            return ExtractedPropertyInfo(
                client_id=client_id,
                full_name=extracted.get("full_name", "N/A"),
                loan_amount=extracted.get("loan_amount", PyDecimal("0")),
                loan_duration=extracted.get("loan_duration", 0),
                property_address=extracted.get("property_address", ""),
                property_description=extracted.get("property_description", ""),
                property_surface=extracted.get("property_surface", 0),
                construction_year=extracted.get("construction_year", 0),
                confidence=PyDecimal("1.0")
            )
            
        except Fault:
            raise
        except Exception as e:
            logger.error(f"[IE] ✗ Erreur: {str(e)}")
            raise Fault("Server.ExtractionError", f"Extraction échouée: {str(e)}")


def _extract_value(text, pattern):
    """Extrait une valeur string du texte selon le pattern"""
    match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
    if match:
        try:
            value = match.group(1).strip()
            if value:
                return value
        except (IndexError, AttributeError):
            pass
    return None


def _extract_number(text, pattern):
    """Extrait une valeur numérique du texte selon le pattern"""
    match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
    if match:
        try:
            value_str = match.group(1).strip()
            return int(value_str)
        except (ValueError, IndexError, AttributeError):
            pass
    return 0


application = Application(
    [InformationExtractionService],
    tns='urn:solvency.verification.service:v1',
    in_protocol=Soap11(validator='lxml'),
    out_protocol=Soap11()
)

wsgi_application = WsgiApplication(application)

if __name__ == '__main__':
    from wsgiref.simple_server import make_server
    logger.info("[IE] 🚀 Démarrage sur :5006")
    server = make_server('0.0.0.0', 5006, wsgi_application)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("[IE] 🛑 Arrêt")
