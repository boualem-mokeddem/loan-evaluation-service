from spyne import (Application, rpc, ServiceBase, Unicode, Decimal, Integer, 
                   Boolean, ComplexModel)
from spyne.protocol.soap import Soap11
from spyne.server.wsgi import WsgiApplication
from spyne.model.fault import Fault
import logging
import json
import uuid
from datetime import datetime
from zeep import Client as SoapClient
from zeep.exceptions import Fault as ZeepFault
from zeep.transports import Transport
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def safe_attr(obj, attr, default=None):
    """Récupère l'attribut de manière sûre depuis un objet Zeep"""
    try:
        value = getattr(obj, attr, default)
        return value
    except Exception as e:
        logger.warning(f"Impossible de récupérer {attr}: {e}")
        return default


ie_client = None
crud_client = None
business_client = None
appraisal_client = None
approval_client = None
notification_client = None


def _create_soap_client(wsdl_url, service_name):
    try:
        session = requests.Session()
        retry = Retry(connect=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        transport = Transport(session=session, timeout=30)
        
        client = SoapClient(wsdl=wsdl_url, transport=transport)
        
        for service in client.wsdl.services.values():
            for port in service.ports.values():
                base_url = wsdl_url.replace('?wsdl', '')
                port.binding_options['address'] = base_url
        
        logger.info(f"[Orchestrator] ✓ {service_name} connecté")
        return client
    except Exception as e:
        logger.warning(f"[Orchestrator] ⚠️ {service_name}: {e}")
        return None


def _init_clients():
    global ie_client, crud_client, business_client, appraisal_client, approval_client, notification_client
    if ie_client is None:
        ie_client = _create_soap_client("http://ie_service:5006/?wsdl", "IE")
        crud_client = _create_soap_client("http://crud_service:5002/?wsdl", "CRUD")
        business_client = _create_soap_client("http://business_service:5003/?wsdl", "Business")
        appraisal_client = _create_soap_client("http://appraisal_service:5005/?wsdl", "Appraisal")
        approval_client = _create_soap_client("http://approval_service:5007/?wsdl", "Approval")
        notification_client = _create_soap_client("http://notification_service:5008/?wsdl", "Notification")


class LoanApplicationResponse(ComplexModel):
    __namespace__ = "urn:solvency.verification.service:v1"
    correlation_id = Unicode(min_occurs=1)
    client_email = Unicode(min_occurs=1)
    timestamp = Unicode(min_occurs=1)
    status = Unicode(min_occurs=1)
    property_info = Unicode
    credit_assessment = Unicode
    property_evaluation = Unicode
    final_decision = Unicode
    simple_explanation = Unicode


class SolvencyVerificationService(ServiceBase):
    """
    Orchestrator principal du flux de traitement
    Séquence: IE → CRUD → Business → Appraisal → Approval → Notification
    """
    
    @rpc(Unicode, Unicode, _returns=LoanApplicationResponse)
    def process_loan_request(self, client_id, request_text):
        correlation_id = str(uuid.uuid4())[:8].upper()
        logger.info(f"[Orchestrator] 🔄 ProcessLoanRequest({client_id}) - {correlation_id}")
        
        try:
            _init_clients()
            
            # ===== 1. VALIDATION CLIENT =====
            client_email = None
            try:
                client_identity = crud_client.service.get_client_identity(client_id)
                client_email = safe_attr(client_identity, "email")
                
                if not client_email:
                    client_email = f"{client_id}@banque.local"
                
                logger.info(f"[Orchestrator] ✓ Client validé - Email: {client_email}")
            except ZeepFault as f:
                error_msg = f.message if hasattr(f, 'message') else str(f)
                logger.error(f"[Orchestrator] ✗ Erreur client: {error_msg}")
                raise Fault("Client.NotFound", error_msg)
            
            # ===== 2. EXTRACTION PROPRIÉTÉ =====
            try:
                extracted = ie_client.service.extract_property_info(client_id, request_text)
                
                property_info_dict = {
                    "loan_amount": float(safe_attr(extracted, "loan_amount", 0)),
                    "loan_duration": safe_attr(extracted, "loan_duration", 0),
                    "property_address": safe_attr(extracted, "property_address", ""),
                    "property_description": safe_attr(extracted, "property_description", ""),
                    "property_surface": safe_attr(extracted, "property_surface", 0),
                    "construction_year": safe_attr(extracted, "construction_year", 0),
                    "extraction_confidence": 1.0
                }
                
                logger.info(f"[Orchestrator] ✓ Extraction réussie")
            except ZeepFault as f:
                error_msg = f.message if hasattr(f, 'message') else str(f)
                logger.error(f"[Orchestrator] ✗ Extraction échouée: {error_msg}")
                raise Fault("Property.IncompleteData", error_msg)
            
            # ===== 3. RÉCUPÉRATION DONNÉES CLIENT =====
            try:
                financials = crud_client.service.get_client_financials(client_id)
                credit_history = crud_client.service.get_client_credit_history(client_id)
                
                monthly_income = float(safe_attr(financials, "monthly_income", 0))
                monthly_expenses = float(safe_attr(financials, "monthly_expenses", 0))
                debt = float(safe_attr(credit_history, "debt", 0))
                late_payments = int(safe_attr(credit_history, "late_payments", 0))
                has_bankruptcy = bool(safe_attr(credit_history, "has_bankruptcy", False))
                
                logger.info(f"[Orchestrator] ✓ Données client chargées")
            except ZeepFault as f:
                error_msg = f.message if hasattr(f, 'message') else str(f)
                logger.error(f"[Orchestrator] ✗ Erreur données: {error_msg}")
                raise Fault("Client.DataError", error_msg)
            
            # ===== 4. SCORING CRÉDIT =====
            try:
                credit_score_result = business_client.service.compute_credit_score(
                    client_id, debt, late_payments, has_bankruptcy
                )
                credit_score = int(safe_attr(credit_score_result, "score", 0))
                grade = safe_attr(credit_score_result, "grade", "D")
                
                logger.info(f"[Orchestrator] ✓ Score crédit: {credit_score}")
            except ZeepFault as f:
                logger.error(f"[Orchestrator] ✗ Erreur scoring: {str(f)}")
                raise Fault("Business.ScoringError", str(f))
            
            # ===== 5. DÉCISION SOLVABILITÉ =====
            try:
                solvency_result = business_client.service.decide_solvency(
                    monthly_income, monthly_expenses, credit_score
                )
                solvency_status = safe_attr(solvency_result, "status", "not_solvent")
                
                logger.info(f"[Orchestrator] ✓ Solvabilité: {solvency_status}")
            except ZeepFault as f:
                logger.error(f"[Orchestrator] ✗ Erreur solvabilité: {str(f)}")
                raise Fault("Business.DecisionError", str(f))
            
            # ===== 6. EXPLICATIONS CRÉDIT =====
            try:
                explanations_result = business_client.service.explain(
                    credit_score, monthly_income, monthly_expenses, debt, 
                    late_payments, has_bankruptcy
                )
                
                credit_expl = safe_attr(explanations_result, "credit_score_explanation", "")
                income_expl = safe_attr(explanations_result, "income_vs_expenses_explanation", "")
                history_expl = safe_attr(explanations_result, "credit_history_explanation", "")
                
                logger.info(f"[Orchestrator] ✓ Explications générées")
            except ZeepFault as f:
                logger.error(f"[Orchestrator] ✗ Erreur explications: {str(f)}")
                raise Fault("Business.ExplanationError", str(f))
            
            # ===== 7. ÉVALUATION PROPRIÉTÉ =====
            property_evaluation_dict = None
            expert_review_needed = False
            appraisal_explanation = ""
            
            try:
                appraisal_result = appraisal_client.service.evaluate_property(
                    property_info_dict["property_address"], 
                    property_info_dict["property_description"], 
                    client_id, 
                    property_info_dict["loan_amount"], 
                    property_info_dict["property_surface"], 
                    property_info_dict["construction_year"]
                )
                
                property_value = float(safe_attr(appraisal_result, "estimated_value", 0))
                is_compliant = bool(safe_attr(appraisal_result, "is_compliant", False))
                valuation_reason = safe_attr(appraisal_result, "valuation_reason", "")
                appraisal_explanation = valuation_reason
                
                property_evaluation_dict = {
                    "estimated_value": property_value,
                    "is_compliant": is_compliant,
                    "reason": valuation_reason,
                    "status": "COMPLETED"
                }
                
                logger.info(f"[Orchestrator] ✓ Appraisal: {property_value}€")
                
            except ZeepFault as f:
                if "RegionNotFound" in str(f):
                    expert_review_needed = True
                    logger.warning(f"[Orchestrator] ⚠️ Expert Review requis")
                    
                    appraisal_explanation = "La région de votre propriété n'est pas dans notre base de données standard. Une évaluation spécialisée par nos experts sera nécessaire."
                    
                    property_evaluation_dict = {
                        "estimated_value": property_info_dict["loan_amount"] * 0.8,
                        "is_compliant": True,
                        "reason": appraisal_explanation,
                        "status": "EXPERT_REVIEW"
                    }
                else:
                    error_msg = f.message if hasattr(f, 'message') else str(f)
                    logger.error(f"[Orchestrator] ✗ Appraisal error: {error_msg}")
                    raise Fault("Property.AppraisalError", error_msg)
            
            property_value = property_evaluation_dict["estimated_value"]
            is_compliant = property_evaluation_dict["is_compliant"]
            
            # ===== 8. DÉCISION D'APPROBATION =====
            try:
                if not expert_review_needed:
                    approval_result = approval_client.service.approve_loan(
                        credit_score, solvency_status, property_value,
                        property_info_dict["loan_amount"], is_compliant, 
                        monthly_income, monthly_expenses
                    )
                    
                    approved = bool(safe_attr(approval_result, "approved", False))
                    decision = safe_attr(approval_result, "decision", "REJETÉE")
                    interest_rate = float(safe_attr(approval_result, "interest_rate", 0.0))
                    justification = safe_attr(approval_result, "justification", "")
                    risk_level = safe_attr(approval_result, "risk_level", "HIGH")
                    simple_explanation = safe_attr(approval_result, "simple_explanation", "")
                    
                    logger.info(f"[Orchestrator] ✓ Décision: {'APPROUVÉE' if approved else 'REJETÉE'}")
                else:
                    approved = False
                    decision = "EN ATTENTE"
                    interest_rate = 0.0
                    justification = "Évaluation experte en cours"
                    risk_level = "EXPERT_REVIEW"
                    simple_explanation = (
                        "Votre demande a reçu une attention particulière. "
                        "La propriété demande une évaluation spécialisée par nos experts. "
                        "Vous serez notifié par email de la décision finale dans 5-7 jours ouvrables."
                    )
                    
            except ZeepFault as f:
                error_msg = f.message if hasattr(f, 'message') else str(f)
                logger.error(f"[Orchestrator] ✗ Erreur approval: {error_msg}")
                raise Fault("Approval.DecisionError", error_msg)
            
            # ===== 9. NOTIFICATION =====
            try:
                status_for_notif = "EXPERT_REVIEW" if expert_review_needed else ("APPROVED" if approved else "REJECTED")
                
                notification_client.service.send_notification(
                    correlation_id, client_id, "", client_email,
                    status_for_notif, simple_explanation
                )
                
                logger.info(f"[Orchestrator] ✓ Email envoyé à {client_email}")
            except ZeepFault as f:
                logger.warning(f"[Orchestrator] ⚠️ Notification failed: {str(f)}")
            
            # ===== RÉPONSE FINALE =====
            final_decision_dict = {
                "approved": approved,
                "decision": decision,
                "interest_rate": interest_rate,
                "justification": justification,
                "risk_level": risk_level
            }
            
            credit_assessment_dict = {
                "score": credit_score,
                "grade": grade,
                "status": solvency_status,
                "explanations": {
                    "credit": credit_expl,
                    "income": income_expl,
                    "history": history_expl
                }
            }
            
            logger.info(f"[Orchestrator] ✅ Workflow terminé - {correlation_id}")
            
            return LoanApplicationResponse(
                correlation_id=correlation_id,
                client_email=client_email,
                timestamp=datetime.utcnow().isoformat(),
                status="SUCCESS",
                property_info=json.dumps(property_info_dict),
                credit_assessment=json.dumps(credit_assessment_dict),
                property_evaluation=json.dumps(property_evaluation_dict),
                final_decision=json.dumps(final_decision_dict),
                simple_explanation=simple_explanation
            )
            
        except Fault:
            raise
        except Exception as e:
            logger.error(f"[Orchestrator] 💥 Erreur: {str(e)}", exc_info=True)
            raise Fault("Server.OrchestrationError", str(e))


application = Application(
    [SolvencyVerificationService],
    tns='urn:solvency.verification.orchestrator:v1',
    in_protocol=Soap11(validator='lxml'),
    out_protocol=Soap11()
)

wsgi_application = WsgiApplication(application)

if __name__ == '__main__':
    from wsgiref.simple_server import make_server
    logger.info("[Orchestrator] 🚀 Démarrage sur :5004")
    server = make_server('0.0.0.0', 5004, wsgi_application)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("[Orchestrator] 🛑 Arrêt")
