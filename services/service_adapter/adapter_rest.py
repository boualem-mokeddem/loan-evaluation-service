from flask import Flask, request, jsonify
from flask_cors import CORS
from zeep import Client as SoapClient
from zeep.exceptions import Fault as ZeepFault
from zeep.transports import Transport
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import requests
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

ORCHESTRATOR_WSDL = "http://orchestrator_service:5004/?wsdl"
orchestrator_client = None

def get_orchestrator_client():
    global orchestrator_client
    if orchestrator_client is None:
        session = requests.Session()
        retry = Retry(connect=5, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        session.timeout = 30
        
        transport = Transport(session=session, timeout=30)
        orchestrator_client = SoapClient(wsdl=ORCHESTRATOR_WSDL, transport=transport)
        
        for service in orchestrator_client.wsdl.services.values():
            for port in service.ports.values():
                port.binding_options['address'] = 'http://orchestrator_service:5004/'
        
        logger.info("[Adapter] ✓ Connecté à l'Orchestrator SOAP")
    return orchestrator_client


def extract_soap_fault_code(fault_string):
    """Extrait le code d'erreur SOAP (ex: 'Client.NotFound' de 'faultcode: Client.NotFound...')"""
    fault_str = str(fault_string)
    
    error_codes = [
        'Client.NotFound', 'Client.ValidationError', 'Client.DataError',
        'Property.NotFound', 'Property.ValidationError', 'Property.IncompleteData',
        'Property.RegionNotFound', 'Property.AppraisalError',
        'Business.ScoringError', 'Business.DecisionError', 'Business.ExplanationError',
        'Approval.DecisionError',
        'Server.OrchestrationError', 'Server.ExtractionError'
    ]
    
    for code in error_codes:
        if code in fault_str:
            return code
    
    return None


def map_soap_error_to_response(fault):
    """Mappe une erreur SOAP à une réponse HTTP avec message explicite"""
    fault_string = str(fault)
    error_code = extract_soap_fault_code(fault_string)
    
    # Extraire le message détaillé
    error_detail = fault.message if hasattr(fault, 'message') else fault_string
    
    logger.error(f"[Adapter] SOAP Error: {error_code} - {error_detail}")
    
    # Mapping des codes d'erreur vers HTTP status et messages
    error_map = {
        'Client.NotFound': (404, f"Client non trouvé. {error_detail}"),
        'Client.ValidationError': (400, f"Identifiant client invalide. {error_detail}"),
        'Client.DataError': (500, f"Erreur d'accès aux données client. {error_detail}"),
        
        'Property.ValidationError': (400, f"Adresse de propriété invalide. {error_detail}"),
        'Property.IncompleteData': (400, f"Champs manquants : {error_detail}"),
        'Property.RegionNotFound': (202, f"La région de la propriété n'est pas reconnue. {error_detail} Votre demande sera traitée par nos experts."),
        'Property.AppraisalError': (400, f"Erreur d'évaluation de propriété. {error_detail}"),
        
        'Business.ScoringError': (500, f"Erreur de calcul du score de crédit. {error_detail}"),
        'Business.DecisionError': (500, f"Erreur d'évaluation de solvabilité. {error_detail}"),
        'Business.ExplanationError': (500, f"Erreur de génération des explications. {error_detail}"),
        
        'Approval.DecisionError': (500, f"Erreur lors de la décision d'approbation. {error_detail}"),
        
        'Server.OrchestrationError': (500, f"Erreur de traitement global. {error_detail}"),
        'Server.ExtractionError': (400, f"Erreur d'extraction des données. {error_detail}"),
    }
    
    if error_code in error_map:
        status_code, message = error_map[error_code]
    else:
        # Fallback pour erreurs non mappées
        if 'NotFound' in fault_string:
            status_code, message = 404, f"Ressource non trouvée. {error_detail}"
        elif 'ValidationError' in fault_string:
            status_code, message = 400, f"Données invalides. {error_detail}"
        elif 'IncompleteData' in fault_string:
            status_code, message = 400, f"Informations incomplètes. {error_detail}"
        else:
            status_code, message = 500, f"Erreur de traitement. {error_detail}"
    
    return status_code, message, error_code or 'Unknown'


@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'service': 'REST Adapter'
    }), 200


@app.route('/api/loan/apply', methods=['POST'])
def apply_loan():
    try:
        data = request.get_json()
        client_id = data.get('client_id')
        request_text = data.get('request_text')
        
        if not client_id or not request_text:
            return jsonify({
                'error': 'Champs manquants : client_id et request_text sont obligatoires',
                'status': 'error'
            }), 400
        
        logger.info(f"[Adapter] 📨 LoanApplication({client_id})")
        
        try:
            soap_response = get_orchestrator_client().service.process_loan_request(client_id, request_text)
            
            # Récupérer les valeurs de manière sûre
            correlation_id = getattr(soap_response, 'correlation_id', '')
            client_email = getattr(soap_response, 'client_email', '') if hasattr(soap_response, 'client_email') else 'non-fourni'
            timestamp = getattr(soap_response, 'timestamp', '')
            
            # Parser les réponses JSON
            property_info = {}
            credit_assessment = {}
            property_evaluation = {}
            final_decision = {}
            simple_explanation = ''
            
            try:
                if hasattr(soap_response, 'property_info') and soap_response.property_info:
                    property_info = json.loads(soap_response.property_info)
            except:
                pass
            
            try:
                if hasattr(soap_response, 'credit_assessment') and soap_response.credit_assessment:
                    credit_assessment = json.loads(soap_response.credit_assessment)
            except:
                pass
            
            try:
                if hasattr(soap_response, 'property_evaluation') and soap_response.property_evaluation:
                    property_evaluation = json.loads(soap_response.property_evaluation)
            except:
                pass
            
            try:
                if hasattr(soap_response, 'final_decision') and soap_response.final_decision:
                    final_decision = json.loads(soap_response.final_decision)
            except:
                pass
            
            try:
                if hasattr(soap_response, 'simple_explanation') and soap_response.simple_explanation:
                    simple_explanation = soap_response.simple_explanation
            except:
                pass
            
            result = {
                'status': 'success',
                'correlation_id': correlation_id,
                'client_email': client_email,
                'timestamp': timestamp,
                'extracted_info': property_info,
                'credit_assessment': credit_assessment,
                'property_evaluation': property_evaluation,
                'final_decision': final_decision,
                'simple_explanation': simple_explanation
            }
            
            logger.info(f"[Adapter] ✅ Traitement réussi - {correlation_id}")
            return jsonify(result), 200
        
        except ZeepFault as f:
            status_code, message, error_code = map_soap_error_to_response(f)
            
            return jsonify({
                'error': message,
                'status': 'error',
                'fault_code': error_code
            }), status_code
        
        except (requests.ConnectionError, requests.Timeout) as e:
            logger.error(f"[Adapter] 🔌 Erreur de connexion: {str(e)}")
            return jsonify({
                'error': f'Services indisponibles. L\'orchestrator ne répond pas. Veuillez réessayer dans quelques instants.',
                'status': 'error',
                'fault_code': 'ConnectivityError'
            }), 503
        
        except Exception as e:
            logger.error(f"[Adapter] ⚠️ Erreur inattendue: {str(e)}", exc_info=True)
            return jsonify({
                'error': f'Erreur serveur interne. {str(e)}',
                'status': 'error',
                'fault_code': 'InternalServerError'
            }), 500
    
    except Exception as e:
        logger.error(f"[Adapter] 💥 Erreur de traitement de requête: {str(e)}")
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500


@app.route('/api/health', methods=['GET'])
def api_health():
    return jsonify({
        'status': 'ok',
        'service': 'Loan Processing API',
        'version': '2.0'
    }), 200


@app.errorhandler(404)
def not_found(e):
    return jsonify({
        'error': 'Endpoint non trouvé',
        'status': 'error'
    }), 404


@app.errorhandler(500)
def internal_error(e):
    logger.error(f"[Adapter] Erreur 500: {str(e)}")
    return jsonify({
        'error': 'Erreur serveur interne',
        'status': 'error'
    }), 500


if __name__ == '__main__':
    logger.info("[Adapter] 🚀 Démarrage sur :5001")
    app.run(host='0.0.0.0', port=5001, debug=False)
