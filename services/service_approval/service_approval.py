from spyne import (Application, rpc, ServiceBase, Unicode, Decimal, Integer, 
                   Boolean, ComplexModel)
from spyne.protocol.soap import Soap11
from spyne.server.wsgi import WsgiApplication
from spyne.model.fault import Fault
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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


def _safe_to_bool(value):
    """Convertit de manière sûre en booléen"""
    try:
        if isinstance(value, bool):
            return value
        s = str(value).lower()
        return s in ['true', '1', 'yes']
    except:
        return False


class ApprovalDecision(ComplexModel):
    __namespace__ = "urn:solvency.verification.service:v1"
    decision = Unicode(min_occurs=1)
    approved = Boolean(min_occurs=1)
    interest_rate = Decimal(min_occurs=1)
    justification = Unicode(min_occurs=1)
    risk_level = Unicode(min_occurs=1)
    simple_explanation = Unicode(min_occurs=1)


class ApprovalService(ServiceBase):
    """
    Service de décision d'approbation
    Combine solvabilité + évaluation propriété + génère la décision
    """
    
    BASE_RATE = 3.0
    
    @rpc(Integer, Unicode, Decimal, Decimal, Boolean, Decimal, Decimal, 
         _returns=ApprovalDecision)
    def approve_loan(ctx, credit_score, solvency_status, property_value, 
                    loan_amount, property_compliant, monthly_income, monthly_expenses):
        """
        Décision d'approbation basée sur :
        1. Score de crédit et solvabilité
        2. LTV (Loan-to-Value ratio)
        3. DTI (Debt-to-Income ratio)
        4. Conformité de la propriété
        """
        logger.info(f"[Approval] ApprovalRequest - Score: {credit_score}")
        
        try:
            # Conversions sûres pour tous les types Zeep
            credit_score_val = _safe_to_int(credit_score)
            solvency_str = str(solvency_status) if solvency_status else "not_solvent"
            property_value_val = _safe_to_float(property_value)
            loan_amount_val = _safe_to_float(loan_amount)
            income_val = _safe_to_float(monthly_income)
            expenses_val = _safe_to_float(monthly_expenses)
            compliant_val = _safe_to_bool(property_compliant)
            
            # Calculs des ratios
            ltv = (loan_amount_val / property_value_val * 100) if property_value_val > 0 else 100
            dti = (expenses_val / income_val * 100) if income_val > 0 else 100
            
            approved, risk_level, justification = _make_decision(
                credit_score_val, solvency_str, ltv, dti, compliant_val
            )
            
            interest_rate = _calculate_interest_rate(
                credit_score_val, risk_level, ltv, dti
            )
            
            simple_explanation = _generate_explanation(
                approved, credit_score_val, risk_level, ltv, dti, compliant_val, justification
            )
            
            decision_text = "✅ APPROUVÉE" if approved else "❌ REJETÉE"
            logger.info(f"[Approval] Décision: {decision_text} | Taux: {interest_rate}% | Risque: {risk_level}")
            
            return ApprovalDecision(
                decision=decision_text,
                approved=approved,
                interest_rate=interest_rate,
                justification=justification,
                risk_level=risk_level,
                simple_explanation=simple_explanation
            )
            
        except Exception as e:
            logger.error(f"[Approval] Erreur: {str(e)}", exc_info=True)
            raise Fault("Server.ApprovalError", f"Erreur de décision: {str(e)}")


def _make_decision(credit_score, solvency_status, ltv, dti, property_compliant):
    """Logique de décision avec seuils"""
    
    if not property_compliant:
        return False, "TRÈS_ÉLEVÉ", "La propriété ne respecte pas les normes de conformité"
    
    if credit_score < 600:
        return False, "TRÈS_ÉLEVÉ", "Score de crédit insuffisant"
    
    if solvency_status != "solvent":
        return False, "ÉLEVÉ", "Profil de solvabilité insuffisant"
    
    if ltv > 95:
        return False, "ÉLEVÉ", "Ratio LTV trop élevé (> 95%)"
    
    if dti > 50:
        return False, "MOYEN", "Ratio DTI trop élevé (> 50%)"
    
    if credit_score >= 800 and ltv <= 80 and dti <= 35:
        return True, "FAIBLE", "Profil excellent"
    elif credit_score >= 700 and ltv <= 85 and dti <= 40:
        return True, "MOYEN", "Profil satisfaisant"
    elif credit_score >= 650 and ltv <= 90 and dti <= 45:
        return True, "MOYEN_ÉLEVÉ", "Profil acceptable"
    else:
        return True, "ÉLEVÉ", "Profil limité - approbation conditionnelle"


def _calculate_interest_rate(credit_score, risk_level, ltv, dti):
    """Calcule le taux d'intérêt basé sur le profil de risque"""
    base_rate = ApprovalService.BASE_RATE
    
    risk_premiums = {
        "FAIBLE": 0.0,
        "MOYEN": 0.75,
        "MOYEN_ÉLEVÉ": 1.5,
        "ÉLEVÉ": 2.5,
        "TRÈS_ÉLEVÉ": 4.0
    }
    
    score_adj = (800 - credit_score) / 100 * 0.3
    ltv_adj = max(0, (ltv - 80) / 100 * 0.2)
    dti_adj = max(0, (dti - 40) / 100 * 0.15)
    
    risk_prem = risk_premiums.get(risk_level, 0.0)
    final_rate = base_rate + risk_prem + score_adj + ltv_adj + dti_adj
    
    return max(2.5, min(8.0, final_rate))


def _generate_explanation(approved, credit_score, risk_level, ltv, dti, compliant, justification):
    """Génère une explication simple et compréhensible pour l'utilisateur"""
    if approved:
        if risk_level == "FAIBLE":
            return (
                "Votre dossier est approuvé avec une évaluation très favorable. "
                "Vous bénéficiez d'un taux d'intérêt compétitif basé sur votre excellent profil financier."
            )
        elif risk_level == "MOYEN":
            return (
                "Votre dossier est approuvé avec une bonne évaluation. "
                "Les conditions standard de crédit s'appliquent à votre situation."
            )
        else:
            return (
                "Votre dossier a été approuvé. "
                "Veuillez consulter les détails pour connaître les conditions spécifiques applicables."
            )
    else:
        if not compliant:
            return (
                "Malheureusement, la propriété ne répond pas aux critères de conformité requis par notre établissement."
            )
        elif credit_score < 600:
            return (
                "Votre score de crédit est actuellement insuffisant. "
                "Nous vous recommandons de nous recontacter après amélioration de votre profil."
            )
        elif dti > 50:
            return (
                "Vos charges mensuelles dépassent le seuil acceptable. "
                "Réduire vos dépenses permettrait de reconsidérer votre demande."
            )
        else:
            return (
                f"Votre demande ne peut pas être approuvée actuellement. Motif: {justification}. "
                "Nous restons disponibles pour discuter de solutions alternatives."
            )


application = Application(
    [ApprovalService],
    tns='urn:solvency.verification.approval:v1',
    in_protocol=Soap11(validator='lxml'),
    out_protocol=Soap11()
)

wsgi_application = WsgiApplication(application)

if __name__ == '__main__':
    from wsgiref.simple_server import make_server
    logger.info("[Approval] 🚀 Démarrage sur :5007")
    server = make_server('0.0.0.0', 5007, wsgi_application)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("[Approval] 🛑 Arrêt")
