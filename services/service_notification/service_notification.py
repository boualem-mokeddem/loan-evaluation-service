# -*- coding: utf-8 -*-
from spyne import (Application, rpc, ServiceBase, Unicode, Boolean, ComplexModel)
from spyne.protocol.soap import Soap11
from spyne.server.wsgi import WsgiApplication
from spyne.model.fault import Fault
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ===== SMTP CONFIGURATION =====
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "loanapp@example.com")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "")
SENDER_NAME = "LoanApp System"

ENABLE_REAL_EMAILS = bool(SENDER_PASSWORD and SENDER_EMAIL != "loanapp@example.com")


class NotificationResponse(ComplexModel):
    __namespace__ = "urn:solvency.verification.service:v1"
    notification_id = Unicode(min_occurs=1)
    status = Unicode(min_occurs=1)
    recipient = Unicode(min_occurs=1)
    message = Unicode(min_occurs=1)


class NotificationService(ServiceBase):
    """Service de notification - Envoie les emails de décision de prêt"""
    
    @rpc(Unicode, Unicode, Unicode, Unicode, Unicode, Unicode, 
         _returns=NotificationResponse)
    def send_notification(ctx, correlation_id, client_id, client_name, 
                         client_email, decision_status, simple_explanation):
        """
        Envoie une notification email au client avec la décision du prêt
        
        Parameters:
        - correlation_id: ID unique de la demande
        - client_id: ID du client
        - client_name: Nom du client
        - client_email: Email du client
        - decision_status: APPROVED, REJECTED, EXPERT_REVIEW
        - simple_explanation: Message explicatif pour le client
        """
        
        logger.info(f"[Notification] SendNotification({correlation_id}) - {decision_status}")
        logger.info(f"[Notification] Client: {client_name} ({client_email})")
        
        try:
            subject = _get_subject(decision_status)
            html_body = _get_email_template(client_name, decision_status, simple_explanation, correlation_id)
            
            if ENABLE_REAL_EMAILS:
                _send_real_email(client_email, subject, html_body)
                logger.info(f"[Email] ✓ Email RÉEL envoyé → {client_email}")
            else:
                logger.info(f"[Email] 📝 Mode simulation (pas d'SMTP configuré)")
                logger.info(f"[Email] → {client_email}: {decision_status}")
                logger.info(f"[Email] Sujet: {subject}")
            
            logger.info(f"[Dashboard] {client_id}: {decision_status}")
            
            notification_id = f"NOTIF-{correlation_id}"
            
            return NotificationResponse(
                notification_id=notification_id,
                status="SENT",
                recipient=client_email,
                message=f"Notification {decision_status} envoyée à {client_email}"
            )
            
        except Exception as e:
            logger.error(f"[Notification] ✗ Erreur: {str(e)}")
            raise Fault("Server.NotificationError", 
                       f"Notification failed: {str(e)}")


def _send_real_email(recipient_email, subject, html_body):
    """Envoie un email réel via SMTP"""
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"{SENDER_NAME} <{SENDER_EMAIL}>"
        msg['To'] = recipient_email
        msg['Date'] = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")
        
        part = MIMEText(html_body, 'html', 'utf-8')
        msg.attach(part)
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        
        logger.info(f"[SMTP] Connecté à {SMTP_SERVER}:{SMTP_PORT}")
        
        server.send_message(msg)
        server.quit()
        
        logger.info(f"[SMTP] ✓ Email envoyé avec succès à {recipient_email}")
        
    except smtplib.SMTPAuthenticationError:
        logger.error("[SMTP] ✗ Erreur d'authentification - vérifier SENDER_EMAIL et SENDER_PASSWORD")
        raise
    except smtplib.SMTPException as e:
        logger.error(f"[SMTP] ✗ Erreur SMTP: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"[SMTP] ✗ Erreur générale: {str(e)}")
        raise


def _get_subject(decision_status):
    """Génère le sujet de l'email selon la décision"""
    subjects = {
        "APPROVED": "✓ Bonne nouvelle! Votre demande de prêt est APPROUVÉE",
        "REJECTED": "✗ Décision concernant votre demande de prêt",
        "EXPERT_REVIEW": "⏳ Votre demande est en cours d'examen"
    }
    return subjects.get(decision_status, "Décision concernant votre demande de prêt")


def _get_email_template(client_name, decision_status, explanation, correlation_id):
    """Génère le template HTML de l'email"""
    
    color_map = {
        "APPROVED": "#28a745",
        "REJECTED": "#dc3545",
        "EXPERT_REVIEW": "#ffc107"
    }
    color = color_map.get(decision_status, "#007bff")
    
    status_emoji = {
        "APPROVED": "✓",
        "REJECTED": "✗",
        "EXPERT_REVIEW": "⏳"
    }
    emoji = status_emoji.get(decision_status, "•")
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: {color}; color: white; padding: 20px; border-radius: 5px; text-align: center; }}
            .content {{ background-color: #f9f9f9; padding: 20px; margin-top: 20px; border-left: 4px solid {color}; }}
            .footer {{ margin-top: 30px; font-size: 12px; color: #666; text-align: center; border-top: 1px solid #ddd; padding-top: 20px; }}
            .status {{ font-size: 24px; margin: 10px 0; }}
            .explanation {{ margin: 20px 0; padding: 15px; background-color: #fff; border-radius: 3px; }}
            .correlation {{ font-size: 12px; color: #999; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>LoanApp Decision</h1>
                <div class="status">{emoji} {decision_status}</div>
            </div>
            
            <div class="content">
                <p>Bonjour <strong>{client_name}</strong>,</p>
                
                <div class="explanation">
                    <p>{explanation}</p>
                </div>
                
                <p>Si vous avez des questions concernant cette décision, n'hésitez pas à nous contacter.</p>
                
                <p>Cordialement,<br>
                <strong>LoanApp System</strong></p>
            </div>
            
            <div class="footer">
                <p>Cet email a été généré automatiquement - Veuillez ne pas répondre à cet email</p>
                <div class="correlation">ID de demande: {correlation_id}</div>
                <p>&copy; 2025 LoanApp. Tous droits réservés.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html


application = Application(
    [NotificationService],
    tns='urn:solvency.verification.notification:v1',
    in_protocol=Soap11(validator='lxml'),
    out_protocol=Soap11()
)

wsgi_application = WsgiApplication(application)

if __name__ == '__main__':
    from wsgiref.simple_server import make_server
    
    if ENABLE_REAL_EMAILS:
        logger.info(f"✓ EMAILS RÉELS ACTIVÉS")
        logger.info(f"  SMTP: {SMTP_SERVER}:{SMTP_PORT}")
        logger.info(f"  From: {SENDER_EMAIL}")
    else:
        logger.info(f"📝 MODE SIMULATION - Pas de SMTP configuré")
        logger.info(f"  Variables d'env requises: SENDER_EMAIL, SENDER_PASSWORD")
    
    logger.info("[Notification] 🚀 Démarrage sur :5008")
    server = make_server('0.0.0.0', 5008, wsgi_application)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("[Notification] 🛑 Arrêt")
