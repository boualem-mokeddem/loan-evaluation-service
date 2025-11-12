from spyne import (Application, rpc, ServiceBase, Unicode, Decimal, Integer, 
                   Boolean, ComplexModel)
from spyne.protocol.soap import Soap11
from spyne.server.wsgi import WsgiApplication
from spyne.model.fault import Fault
import logging
from decimal import Decimal as PyDecimal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CreditScore(ComplexModel):
    __namespace__ = "urn:solvency.verification.service:v1"
    score = Integer(min_occurs=1)
    grade = Unicode(min_occurs=1)


class SolvencyDecision(ComplexModel):
    __namespace__ = "urn:solvency.verification.service:v1"
    status = Unicode(min_occurs=1)
    is_solvent = Boolean(min_occurs=1)


class ExplanationData(ComplexModel):
    __namespace__ = "urn:solvency.verification.service:v1"
    credit_score_explanation = Unicode(min_occurs=1)
    income_vs_expenses_explanation = Unicode(min_occurs=1)
    credit_history_explanation = Unicode(min_occurs=1)


class CreditScoringService(ServiceBase):
    """
    Service de calcul du score de crédit
    Formule: 1000 - 0.1*dette - 50*retards - (faillite?200:0)
    """
    
    @rpc(Unicode, Decimal, Integer, Boolean, _returns=CreditScore)
    def compute_credit_score(ctx, client_id, debt, late_payments, has_bankruptcy):
        logger.info(f"[Business] ComputeScore({client_id})")
        
        try:
            debt_val = float(debt) if debt else 0
            late_pay_val = int(late_payments) if late_payments else 0
            bankruptcy_penalty = 200 if has_bankruptcy else 0
            
            score = int(1000 - 0.1 * debt_val - 50 * late_pay_val - bankruptcy_penalty)
            score = max(0, min(1000, score))
            
            grade = _get_grade(score)
            logger.info(f"[Business] Score: {score} ({grade})")
            
            return CreditScore(score=score, grade=grade)
        except Exception as e:
            logger.error(f"[Business] Erreur scoring: {str(e)}")
            raise Fault("Server.CalculationError", f"Erreur de calcul: {str(e)}")


class SolvencyDecisionService(ServiceBase):
    """
    Service de décision de solvabilité
    Critères: score >= 700 ET revenu > dépenses
    """
    
    @rpc(Decimal, Decimal, Integer, _returns=SolvencyDecision)
    def decide_solvency(ctx, monthly_income, monthly_expenses, score):
        logger.info(f"[Business] DecideSolvency(score={score})")
        
        try:
            income_val = float(monthly_income) if monthly_income else 0
            expenses_val = float(monthly_expenses) if monthly_expenses else 0
            score_val = int(score) if score else 0
            
            is_solvent = (score_val >= 700) and (income_val > expenses_val)
            status = "solvent" if is_solvent else "not_solvent"
            
            logger.info(f"[Business] Solvabilité: {status}")
            return SolvencyDecision(status=status, is_solvent=is_solvent)
        except Exception as e:
            logger.error(f"[Business] Erreur solvabilité: {str(e)}")
            raise Fault("Server.DecisionError", f"Erreur de décision: {str(e)}")


class ExplanationService(ServiceBase):
    """
    Service de génération d'explications
    Langage simple et compréhensible, sans jargon technique
    """
    
    @rpc(Integer, Decimal, Decimal, Decimal, Integer, Boolean, 
         _returns=ExplanationData)
    def explain(ctx, score, monthly_income, monthly_expenses, debt, 
                late_payments, has_bankruptcy):
        logger.info(f"[Business] GenerateExplanations(score={score})")
        
        try:
            score_val = int(score) if score else 0
            income_val = float(monthly_income) if monthly_income else 0
            expenses_val = float(monthly_expenses) if monthly_expenses else 0
            debt_val = float(debt) if debt else 0
            late_pay_val = int(late_payments) if late_payments else 0
            
            # Explication Score de Crédit
            if score_val >= 800:
                cs_expl = (
                    f"✓ Excellent ! Votre score de crédit est très bon ({score_val}/1000). "
                    f"Vous avez un historique financier solide et fiable."
                )
            elif score_val >= 700:
                cs_expl = (
                    f"✓ Satisfaisant. Votre score de crédit est bon ({score_val}/1000). "
                    f"Vous êtes dans une position favorable pour obtenir un crédit."
                )
            elif score_val >= 600:
                cs_expl = (
                    f"⚠ Moyen. Votre score de crédit est acceptable ({score_val}/1000), "
                    f"mais il y a des domaines à améliorer."
                )
            else:
                cs_expl = (
                    f"✗ Faible. Votre score de crédit est bas ({score_val}/1000). "
                    f"Nous vous recommandons d'améliorer votre historique de paiement avant de faire une nouvelle demande."
                )
            
            # Explication Revenus vs Dépenses
            diff = income_val - expenses_val
            if income_val <= expenses_val:
                ie_expl = (
                    f"✗ Attention. Vos dépenses mensuelles (${expenses_val:,.0f}) "
                    f"égalent ou dépassent vos revenus (${income_val:,.0f}). "
                    f"C'est un point de préoccupation pour notre évaluation."
                )
            else:
                pct_savings = (diff / income_val * 100) if income_val > 0 else 0
                ie_expl = (
                    f"✓ Positif. Vous avez une capacité d'épargne de ${diff:,.0f} par mois "
                    f"({pct_savings:.1f}% de vos revenus). C'est un facteur favorable."
                )
            
            # Explication Historique de Crédit
            if has_bankruptcy:
                ch_expl = (
                    f"✗ Vous avez une faillite antérieure dans votre dossier. "
                    f"C'est un facteur significatif qui affecte notre évaluation. "
                    f"Votre dossier crédit actuel: ${debt_val:,.0f} de dette."
                )
            elif late_pay_val > 0:
                ch_expl = (
                    f"⚠ Vous avez {late_pay_val} paiement(s) en retard antérieurement. "
                    f"Vos dettes actuelles totalisent ${debt_val:,.0f}. "
                    f"Un paiement à jour depuis est positif."
                )
            else:
                ch_expl = (
                    f"✓ Parfait ! Vous n'avez aucun paiement en retard. "
                    f"Votre historique est solide (dettes actuelles: ${debt_val:,.0f})."
                )
            
            logger.info("[Business] ✓ Explications générées")
            
            return ExplanationData(
                credit_score_explanation=cs_expl,
                income_vs_expenses_explanation=ie_expl,
                credit_history_explanation=ch_expl
            )
        except Exception as e:
            logger.error(f"[Business] Erreur explications: {str(e)}")
            raise Fault("Server.ExplanationError", f"Erreur de génération: {str(e)}")


def _get_grade(score):
    """Échelle de notation du crédit"""
    if score >= 850:
        return "A+"
    elif score >= 800:
        return "A"
    elif score >= 700:
        return "B"
    elif score >= 600:
        return "C"
    else:
        return "D"


application = Application(
    [CreditScoringService, SolvencyDecisionService, ExplanationService],
    tns='urn:solvency.verification.business:v1',
    in_protocol=Soap11(validator='lxml'),
    out_protocol=Soap11()
)

wsgi_application = WsgiApplication(application)

if __name__ == '__main__':
    from wsgiref.simple_server import make_server
    logger.info("[Business] 🚀 Démarrage sur :5003")
    server = make_server('0.0.0.0', 5003, wsgi_application)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("[Business] 🛑 Arrêt")
