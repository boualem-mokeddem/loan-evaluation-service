const API_URL = 'http://localhost:5001';

const STEPS = [
    "Extraction des informations",
    "Validation du client",
    "Analyse financière",
    "Évaluation de propriété",
    "Décision d'approbation",
    "Envoi de notification"
];

const ERROR_MESSAGES = {
    "Client.NotFound": "Client non trouvé dans notre système. Veuillez vérifier l'identifiant client.",
    "Client.ValidationError": "Format d'identifiant client invalide. Utilisez le format 'client-XXX'.",
    "Property.IncompleteData": "Champs manquants ou invalides. Veuillez vérifier :",
    "Property.ValidationError": "Adresse de propriété invalide. Elle est trop courte ou vide.",
    "Property.RegionNotFound": "La région de la propriété n'est pas dans notre base de données standard. Votre demande sera traitée par nos experts spécialisés.",
    "Client.DataError": "Impossible de récupérer les données client. Erreur base de données.",
    "Business.ScoringError": "Erreur lors du calcul du score de crédit.",
    "Business.DecisionError": "Erreur lors de l'évaluation de solvabilité.",
    "Approval.DecisionError": "Erreur lors de la prise de décision. Veuillez réessayer.",
    "Property.AppraisalError": "Erreur lors de l'évaluation de la propriété.",
    "Server.OrchestrationError": "Erreur de traitement global. Le système n'a pas pu compléter l'évaluation."
};

let lastFormData = null;
let currentCorrelationId = null;

document.getElementById('loanForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const requestText = document.getElementById('requestText').value;

    if (!requestText || requestText.trim().length < 20) {
        showError("Veuillez entrer les informations de demande complètes");
        return;
    }

    showLoading(true);
    hideError();
    hideResult();
    checkServiceStatus();

    lastFormData = {
        request_text: requestText,
        client_id: extractClientId(requestText)
    };

    try {
        const response = await fetch(`${API_URL}/api/loan/apply`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                client_id: lastFormData.client_id,
                request_text: requestText
            })
        });

        const data = await response.json();
        
        if (!response.ok) {
            const errorMsg = parseErrorMessage(data);
            throw new Error(errorMsg);
        }

        if (data.status === 'success') {
            displayResult(data);
            document.getElementById('formSection').style.display = 'none';
        } else {
            throw new Error(data.error || 'Erreur de traitement inconnue');
        }

    } catch (error) {
        console.error('Error:', error);
        showError(error.message);
    } finally {
        showLoading(false);
    }
});

function extractClientId(text) {
    const match = text.match(/CLIENT_ID\s*:\s*([^\n]+)/i);
    return match ? match[1].trim() : 'unknown';
}

function parseErrorMessage(data) {
    if (!data.error) return "Erreur inconnue";
    
    const errorStr = data.error;
    
    for (const [code, message] of Object.entries(ERROR_MESSAGES)) {
        if (errorStr.includes(code) || errorStr.toLowerCase().includes(code.toLowerCase())) {
            if (errorStr.length > code.length) {
                const detail = errorStr.split(':').slice(1).join(':').trim();
                return message + (detail ? "\n\n" + detail : "");
            }
            return message;
        }
    }
    
    if (errorStr.includes('NotFound')) {
        return "La ressource demandée n'existe pas dans notre système.";
    } else if (errorStr.includes('ValidationError')) {
        return "Les données fournies ne sont pas au bon format.";
    } else if (errorStr.includes('IncompleteData')) {
        return "Informations incomplètes. Tous les champs sont obligatoires.";
    } else if (errorStr.includes('RegionNotFound')) {
        return "La région de la propriété n'est pas reconnue. Une évaluation experte sera nécessaire.";
    }
    
    return errorStr;
}

function displayResult(data) {
    const decision = data.final_decision || {};
    const isApproved = decision.approved;
    const propertyEval = data.property_evaluation || {};
    
    currentCorrelationId = data.correlation_id;

    const decisionTitle = document.getElementById('decisionTitle');
    const decisionNumber = document.getElementById('decisionNumber');
    const decisionReason = document.getElementById('decisionReason');
    const decisionBrick = document.querySelector('.decision-brick');

    if (isApproved) {
        decisionBrick.className = 'decision-brick approved';
        decisionTitle.textContent = '✅ APPROUVÉE';
    } else if (decision.decision === 'EN ATTENTE') {
        decisionBrick.className = 'decision-brick pending';
        decisionTitle.textContent = '⏳ EN ATTENTE';
    } else {
        decisionBrick.className = 'decision-brick rejected';
        decisionTitle.textContent = '❌ REJETÉE';
    }

    decisionNumber.textContent = `Demande N° ${data.correlation_id}`;
    decisionReason.textContent = decision.justification || decision.decision || 'Pas de motif disponible';

    // Credit Assessment
    const creditAssess = data.credit_assessment || {};
    document.getElementById('creditScore').textContent = 
        creditAssess.score ? `${creditAssess.score}/1000 (${creditAssess.grade || 'N/A'})` : '-';
    
    const solvencyText = creditAssess.status === 'solvent' ? '✓ Solvable' : '✗ Non solvable';
    document.getElementById('solvencyStatus').textContent = solvencyText;

    // Property Evaluation
    document.getElementById('propertyValue').textContent = 
        propertyEval.estimated_value ? `${Number(propertyEval.estimated_value).toLocaleString('fr-FR', {style: 'currency', currency: 'EUR'})}` : '-';
    
    document.getElementById('riskLevel').textContent = decision.risk_level || '-';

    // Explications
    const explanations = creditAssess.explanations || {};
    const explanationHtml = buildExplanationsSection(
        explanations.credit,
        explanations.income,
        explanations.history,
        propertyEval.reason
    );
    document.getElementById('explanations').innerHTML = explanationHtml;

    // Client email
    document.getElementById('clientEmail').textContent = data.client_email || 'adresse-email@domaine.com';

    // Hide analysis by default
    document.getElementById('analysisSection').style.display = 'none';

    document.getElementById('resultSection').style.display = 'block';
    window.scrollTo(0, document.querySelector('.result-section').offsetTop - 100);
}

function buildExplanationsSection(creditExpl, incomeExpl, historyExpl, propertyExpl) {
    return `
        <div class="explanation-subsection">
            <h4>💰 Analyse Financière</h4>
            <div class="explanation-item">
                <p class="explanation-title">Score de crédit :</p>
                <p class="explanation-text">${creditExpl || 'N/A'}</p>
            </div>
            <div class="explanation-item">
                <p class="explanation-title">Revenus vs Dépenses :</p>
                <p class="explanation-text">${incomeExpl || 'N/A'}</p>
            </div>
            <div class="explanation-item">
                <p class="explanation-title">Historique de crédit :</p>
                <p class="explanation-text">${historyExpl || 'N/A'}</p>
            </div>
        </div>

        <div class="explanation-subsection">
            <h4>🏘️ Évaluation de Propriété</h4>
            <div class="explanation-item">
                <p class="explanation-title">Analyse appraisal :</p>
                <p class="explanation-text">${propertyExpl || 'N/A'}</p>
            </div>
        </div>
    `;
}

function toggleAnalysis() {
    const analysisSection = document.getElementById('analysisSection');
    const button = document.querySelector('.btn-toggle-details');
    
    if (analysisSection.style.display === 'none') {
        analysisSection.style.display = 'block';
        button.textContent = '📖 Masquer l\'analyse détaillée';
    } else {
        analysisSection.style.display = 'none';
        button.textContent = '📖 Afficher l\'analyse détaillée';
    }
}

function showLoading(show) {
    const loading = document.getElementById('loading');
    if (show) {
        loading.style.display = 'block';
        simulateProgress();
    } else {
        loading.style.display = 'none';
    }
}

function simulateProgress() {
    let step = 0;
    const interval = setInterval(() => {
        if (step < STEPS.length) {
            const progress = ((step + 1) / STEPS.length) * 100;
            document.getElementById('progressFill').style.width = progress + '%';
            document.getElementById('progressText').textContent = `${STEPS[step]}...`;
            step++;
        } else {
            clearInterval(interval);
        }
    }, 600);
}

function showError(message) {
    const lines = message.split('\n');
    let htmlContent = lines[0] + '<br>';
    
    if (lines.length > 1) {
        htmlContent += '<ul style="margin-top: 10px; text-align: left;">';
        for (let i = 1; i < lines.length; i++) {
            if (lines[i].trim()) {
                htmlContent += '<li>' + lines[i] + '</li>';
            }
        }
        htmlContent += '</ul>';
    }
    
    document.getElementById('errorMessage').innerHTML = htmlContent;
    document.getElementById('errorSection').style.display = 'block';
}

function hideError() {
    document.getElementById('errorSection').style.display = 'none';
}

function hideResult() {
    document.getElementById('resultSection').style.display = 'none';
}

function resetForm() {
    document.getElementById('loanForm').reset();
    document.getElementById('formSection').style.display = 'block';
    hideResult();
    hideError();
}

function retryRequest() {
    if (lastFormData) {
        document.getElementById('requestText').value = lastFormData.request_text;
        document.getElementById('loanForm').dispatchEvent(new Event('submit'));
    }
}

function checkServiceStatus() {
    fetch(`${API_URL}/api/health`)
        .then(r => r.json())
        .then(data => {
            document.getElementById('statusIndicator').className = 'status-dot active';
            document.getElementById('statusText').textContent = ' Services Actifs';
        })
        .catch(() => {
            document.getElementById('statusIndicator').className = 'status-dot inactive';
            document.getElementById('statusText').textContent = ' Services Indisponibles';
        });
}

checkServiceStatus();
setInterval(checkServiceStatus, 15000);

console.log('✓ Interface chargée');

function showLoading(show) {
    const loading = document.getElementById('loading');
    if (show) {
        loading.style.display = 'block';
        simulateProgress();
    } else {
        loading.style.display = 'none';
    }
}

function simulateProgress() {
    let step = 0;
    const interval = setInterval(() => {
        if (step < STEPS.length) {
            const progress = ((step + 1) / STEPS.length) * 100;
            document.getElementById('progressFill').style.width = progress + '%';
            document.getElementById('progressText').textContent = `${STEPS[step]}...`;
            step++;
        } else {
            clearInterval(interval);
        }
    }, 600);
}

function showError(message) {
    const lines = message.split('\n');
    let htmlContent = lines[0] + '<br>';
    
    if (lines.length > 1) {
        htmlContent += '<ul style="margin-top: 10px; text-align: left;">';
        for (let i = 1; i < lines.length; i++) {
            if (lines[i].trim()) {
                htmlContent += '<li>' + lines[i] + '</li>';
            }
        }
        htmlContent += '</ul>';
    }
    
    document.getElementById('errorMessage').innerHTML = htmlContent;
    document.getElementById('errorSection').style.display = 'block';
}

function hideError() {
    document.getElementById('errorSection').style.display = 'none';
}

function hideResult() {
    document.getElementById('resultSection').style.display = 'none';
}

function resetForm() {
    document.getElementById('loanForm').reset();
    document.getElementById('formSection').style.display = 'block';
    hideResult();
    hideError();
}

function retryRequest() {
    if (lastFormData) {
        document.getElementById('requestText').value = lastFormData.request_text;
        document.getElementById('loanForm').dispatchEvent(new Event('submit'));
    }
}

function checkServiceStatus() {
    fetch(`${API_URL}/api/health`)
        .then(r => r.json())
        .then(data => {
            document.getElementById('statusIndicator').className = 'status-dot active';
            document.getElementById('statusText').textContent = ' Services Actifs';
        })
        .catch(() => {
            document.getElementById('statusIndicator').className = 'status-dot inactive';
            document.getElementById('statusText').textContent = ' Services Indisponibles';
        });
}

checkServiceStatus();
setInterval(checkServiceStatus, 15000);

console.log('✓ Interface chargée');
