# -*- coding: utf-8 -*-
from spyne import (Application, rpc, ServiceBase, Unicode, Decimal, Boolean, 
                   ComplexModel, Integer)
from spyne.protocol.soap import Soap11
from spyne.server.wsgi import WsgiApplication
from spyne.model.fault import Fault
import logging
import re
import json
from zeep import Client as SoapClient
from zeep.transports import Transport
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def safe_attr(obj, attr, default=None):
    """Récupère l'attribut de manière sûre depuis un objet Zeep"""
    try:
        return getattr(obj, attr, default)
    except:
        return default


# Base de données des régions avec données de marché
LOCAL_REGION_CACHE = {
    "boston": {
        "base_price_m2": 450000,
        "comparables": [
            {"address": "Boston MA", "price": 350000, "surface": 2000, "year": 2005},
            {"address": "Boston MA", "price": 420000, "surface": 2200, "year": 2012},
            {"address": "Boston MA", "price": 380000, "surface": 1900, "year": 1985},
        ]
    },
    "nyc": {
        "base_price_m2": 650000,
        "comparables": [
            {"address": "NYC NY", "price": 550000, "surface": 1200, "year": 2010},
            {"address": "NYC NY", "price": 620000, "surface": 1400, "year": 2015},
            {"address": "NYC NY", "price": 480000, "surface": 1000, "year": 1990},
        ]
    },
    "la": {
        "base_price_m2": 380000,
        "comparables": [
            {"address": "LA CA", "price": 350000, "surface": 2000, "year": 2008},
            {"address": "LA CA", "price": 420000, "surface": 2200, "year": 2018},
            {"address": "LA CA", "price": 320000, "surface": 1800, "year": 2000},
        ]
    }
}


class PropertyEvaluation(ComplexModel):
    __namespace__ = "urn:solvency.verification.service:v1"
    property_address = Unicode(min_occurs=1)
    estimated_value = Decimal(min_occurs=1)
    is_compliant = Boolean(min_occurs=1)
    valuation_reason = Unicode(min_occurs=1)
    evaluation_status = Unicode(min_occurs=1)


def _safe_to_int(value):
    """Convertit de manière sûre un type Zeep en int"""
    try:
        return int(float(str(value)))
    except:
        return 0


def _safe_to_float(value):
    """Convertit de manière sûre un type Zeep en float"""
    try:
        return float(str(value))
    except:
        return 0.0


def _safe_to_str(value):
    """Convertit de manière sûre en string"""
    try:
        return str(value) if value else ""
    except:
        return ""


class AppraisalService(ServiceBase):
    """
    Service d'évaluation de propriété
    - Utilise données de marché locales
    - Évalue propriété avec données comparables
    - Retourne avis d'expert si région inconnue
    """
    
    @rpc(Unicode, Unicode, Unicode, Decimal, Integer, Integer, _returns=PropertyEvaluation)
    def evaluate_property(ctx, property_address, property_description, client_id, 
                         loan_amount, property_surface, construction_year):
        """
        Évaluation de propriété - Extraction ville, recherche marché, calcul valeur
        """
        
        try:
            # Conversions sûres pour tous types Zeep
            addr_str = _safe_to_str(property_address)
            loan_val = _safe_to_float(loan_amount) if loan_amount else 200000.0
            surface_val = _safe_to_int(property_surface) if property_surface else 100
            year_val = _safe_to_int(construction_year) if construction_year else 2000
            
            logger.info(f"[Appraisal] EvaluateProperty - {addr_str[:30]}")
            
            if not addr_str or len(addr_str.strip()) < 3:
                raise Fault("Property.ValidationError", "Adresse de propriété invalide")
            
            city = _extract_city_from_address(addr_str)
            
            if city.lower() not in LOCAL_REGION_CACHE:
                logger.warning(f"[Appraisal] ⚠️ Région '{city}' inconnue")
                raise Fault("Property.RegionNotFound", 
                           f"La région '{city}' n'est pas dans notre base. Expertise requise.")
            
            market = LOCAL_REGION_CACHE[city.lower()]
            comparables = market.get("comparables", [])
            
            if comparables:
                avg_price = sum(c["price"] for c in comparables) / len(comparables)
                avg_surface = sum(c["surface"] for c in comparables) / len(comparables)
            else:
                avg_price = 400000.0
                avg_surface = 100.0
            
            # Ajustements basés sur surface et âge
            surface_diff = float(surface_val) - avg_surface
            surface_factor = 1.0 + (surface_diff * 0.005)
            
            property_age = 2024 - year_val
            if property_age <= 5:
                age_factor = 1.10
            elif property_age <= 15:
                age_factor = 1.0
            elif property_age <= 30:
                age_factor = 0.95
            else:
                age_factor = 0.85
            
            estimated_value = int(avg_price * surface_factor * age_factor)
            is_compliant = _check_compliance(addr_str, year_val)
            
            # Explication humanisée
            reason = _build_appraisal_explanation(
                estimated_value, city, surface_val, property_age, age_factor, is_compliant
            )
            
            logger.info(f"[Appraisal] ✓ Valeur: ${estimated_value:,} | {city} | Conforme: {is_compliant}")
            
            return PropertyEvaluation(
                property_address=addr_str,
                estimated_value=estimated_value,
                is_compliant=is_compliant,
                valuation_reason=reason,
                evaluation_status="COMPLETED"
            )
            
        except Fault as f:
            raise
        except Exception as e:
            logger.error(f"[Appraisal] Erreur: {str(e)}", exc_info=True)
            raise Fault("Server.AppraisalError", f"Évaluation échouée: {str(e)}")


def _extract_city_from_address(address):
    """Extrait la ville de l'adresse"""
    addr_str = _safe_to_str(address).lower()
    parts = addr_str.split(',')
    if len(parts) >= 1:
        last_part = parts[-1].strip().split()
        if last_part:
            return last_part[0]
    return "default"


def _check_compliance(address, construction_year):
    """Vérification de conformité"""
    year_int = _safe_to_int(construction_year) if construction_year else 2000
    
    if year_int < 1970:
        logger.warning(f"[Appraisal] ✗ Propriété antérieure à 1970")
        return False
    
    risk_keywords = [
        "dispute", "damage", "flood", "condemned",
        "non-conforme", "dangereux", "effondrement", "interdit", "zone rouge"
    ]
    
    text = (_safe_to_str(address) + " " + _safe_to_str(construction_year)).lower()
    for keyword in risk_keywords:
        if keyword in text:
            logger.warning(f"[Appraisal] ✗ Risque détecté: {keyword}")
            return False
    
    return True


def _build_appraisal_explanation(value, city, surface, age, age_factor, compliant):
    """Construit une explication humanisée de l'évaluation"""
    
    value_str = f"${value:,}"
    
    # Analyse de l'âge
    if age <= 5:
        age_desc = "Propriété très récente en bon état"
        age_detail = f"+10% pour récence"
    elif age <= 15:
        age_desc = "Propriété moderne, bien entretenue"
        age_detail = "Valeur standard pour cet âge"
    elif age <= 30:
        age_desc = "Propriété d'âge moyen"
        age_detail = "-5% pour l'âge"
    else:
        age_desc = "Propriété ancienne"
        age_detail = "-15% pour l'ancienneté"
    
    # Analyse de la surface
    surface_note = f"{surface} m² (petit)" if surface < 1500 else (
        f"{surface} m² (moyen)" if surface < 2500 else f"{surface} m² (grand)"
    )
    
    # Conformité
    compliance_text = (
        "✓ La propriété respecte toutes les normes de conformité."
        if compliant else
        "✗ La propriété présente des problèmes de conformité."
    )
    
    explanation = (
        f"Valeur estimée: {value_str}. "
        f"Région: {city.capitalize()}. "
        f"Surface: {surface_note}. "
        f"État: {age_desc} ({age_detail}). "
        f"{compliance_text}"
    )
    
    return explanation


application = Application(
    [AppraisalService],
    tns='urn:solvency.verification.appraisal:v1',
    in_protocol=Soap11(validator='lxml'),
    out_protocol=Soap11()
)

wsgi_application = WsgiApplication(application)

if __name__ == '__main__':
    from wsgiref.simple_server import make_server
    logger.info("[Appraisal] 🚀 Démarrage sur :5005")
    server = make_server('0.0.0.0', 5005, wsgi_application)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("[Appraisal] 🛑 Arrêt")
