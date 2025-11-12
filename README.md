# Service Web Composite : Évaluation de Demande de Prêt Immobilier

**Architecture Orientée Services (SOA) avec SOAP/WSDL et Docker**

---

## 📋 Table des Matières

1. [Vue d'ensemble](#vue-densemble)
2. [Prérequis](#prérequis)
3. [Architecture](#architecture)
4. [Installation & Build](#installation--build)
5. [Démarrage](#démarrage)
6. [Utilisation](#utilisation)
7. [Endpoints & WSDL](#endpoints--wsdl)
8. [Exemples de Requêtes/Réponses](#exemples-de-requêtesréponses)
9. [Stratégie de Tests](#stratégie-de-tests)
10. [SLA & QoS](#sla--qos)
11. [Limitations & Améliorations Futures](#limitations--améliorations-futures)

---

## Vue d'ensemble

Ce service composite évalue la **solvabilité des clients** en calculant un score de crédit et une décision d'approbation basée sur :

- **Profil client** : nom, adresse, email
- **Données financières** : revenus/dépenses mensuels
- **Historique de crédit** : dettes, retards de paiement, faillites
- **Évaluation de propriété** : estimation de valeur, conformité
- **Décision d'approbation** : LTV, DTI, risque, taux d'intérêt

### Architecture SOA complète

```
┌─────────────────────────────────────────────────────────────────┐
│                    Web Interface (Flask)                        │
│                      :5000 - HTML/CSS/JS                        │
└──────────────┬──────────────────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────────────────┐
│              REST Adapter (Flask)                               │
│              :5001 - /api/loan/apply                            │
│              Converts REST → SOAP                               │
└──────────────┬──────────────────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────────────────┐
│          Service d'Orchestration SOAP (Spyne)                   │
│          :5004 - Orchester les sous-services                    │
└───┬───────────┬───────────┬───────────┬───────────┬──────────┬──┘
    │           │           │           │           │          │
┌───▼──┐    ┌───▼──┐    ┌───▼──┐    ┌───▼───┐   ┌───▼──┐    ┌──▼──┐
│ IE   │    │ CRUD │    │ BUSI │    │APPRAIS│   │APPROV│    │NOTIF│
│:5006 │    │:5002 │    │:5003 │    │ :5005 │   │:5007 │    │:5008│
└──────┘    └──────┘    └──────┘    └───────┘   └──────┘    └─────┘
```

---

## Prérequis

### Systèmes supportés
- **Linux** (Ubuntu 20.04+, Debian 11+)
- **macOS** (Monterey+, via Docker Desktop)
- **Windows 10+** (WSL2 + Docker Desktop)

### Dépendances obligatoires

1. **Docker** ≥ 28.5.1
   ```bash
   docker --version
   ```

2. **Docker Compose** ≥ 2.40.2
   ```bash
   docker-compose --version
   ```

3. **Git** (pour cloner le projet)

### Dépendances optionnelles (développement)

- **Python 3.9+** (pour tests locaux sans Docker)
- **curl** ou **Postman** (pour tester les endpoints)
- **SoapUI Community** (pour tests graphiques)

---

## Architecture

### Services SOAP (Spyne)

| Service                         | Port | Namespace                                   | Responsabilités                                        |
|---------------------------------|------|---------------------------------------------|--------------------------------------------------------|
| **IE** (Information Extraction) | 5006 | `urn:solvency.verification.service:v1`      | Parse requête texte, extrait champs structurés         |
| **CRUD** (Client Directory)     | 5002 | `urn:solvency.verification.crud:v1`         | Lecture données client (identity, financial, credit)   |
| **Business** (Scoring)          | 5003 | `urn:solvency.verification.business:v1`     | Calcul score, décision solvabilité, explications       |
| **Appraisal** (Propriété)       | 5005 | `urn:solvency.verification.appraisal:v1`    | Évaluation propriété, comparables de marché            |
| **Approval** (Décision)         | 5007 | `urn:solvency.verification.approval:v1`     | Décision prêt, LTV, DTI, taux intérêt                  |
| **Notification**                | 5008 | `urn:solvency.verification.notification:v1` | Envoi email décision client                            |
| **Orchestration**               | 5004 | `urn:solvency.verification.orchestrator:v1` | Compose les services, retourne rapport                 |

### Services Utility (Flask)

| Service           | Port | Responsabilités                          |
|-------------------|------|------------------------------------------|
| **Adapter REST**  | 5001 | Proxy REST → SOAP, gestion erreurs, JSON |
| **Web Interface** | 5000 | Interface HTML/JS, appelle :5001         |

### Formules de calcul

**Score de crédit :**
```
score = 1000 - (0.1 × dette) - (50 × retards) - (faillite ? 200 : 0)
score = max(0, min(1000, score))  // Clampé entre 0 et 1000
```

**Solvabilité :**
```
solvent ⟺ (score ≥ 700) ∧ (revenus > dépenses)
```

**LTV (Loan-to-Value) :**
```
LTV = (montant_prêt / valeur_propriété) × 100%
Seuil max : 95%
```

**DTI (Debt-to-Income) :**
```
DTI = (dépenses_mensuelles / revenus_mensuels) × 100%
Seuil max : 50%
```

---

## Installation & Build

### 1. Cloner/Télécharger le projet

```bash
git clone <repo-url> loan-evaluation-service
cd loan-evaluation-service
```

### 2. Structure attendue

```
loan-evaluation-service/
├── services/
│   ├── service_ie/
│   │   ├── service_ie.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── service_crud/
│   │   ├── service_crud.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── service_business/
│   │   ├── service_business.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── service_appraisal/
│   │   ├── service_appraisal.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── service_approval/
│   │   ├── service_approval.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── service_notification/
│   │   ├── service_notification.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── service_orchestrator/
│   │   ├── service_orchestrator.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── service_adapter/
│   │   ├── adapter_rest.py
│   │   └── Dockerfile
│   └── interface/
│       ├── app.py
│       ├── index.html
│       ├── style.css
│       ├── script.js
│       └── Dockerfile
├── tests/
│   ├── test_services.py
│   ├── test_integration.py
│   ├── metrics.py
│   ├── sla_metrics.py
│   └── requirements_test.txt
├── docker-compose.yml
├── README.md 
└── .env
```

### 3. Build des images Docker

```bash
# Option 1 : Docker Compose (recommandé)
docker-compose build

# Option 2 : Build manuel
docker build -t solvency-ie ./services/service_ie
docker build -t solvency-crud ./services/service_crud
docker build -t solvency-business ./services/service_business
# ... etc pour chaque service
```

### 4. Vérifier les images

```bash
docker images 
```

---

## Démarrage

### Mode Production (Docker Compose)

```bash
# Démarrer tous les services
docker-compose up -d

# Vérifier l'état
docker-compose ps

# Voir les logs
docker-compose logs -f

# Logs d'un service spécifique
docker-compose logs -f orchestrator_service
```

**Output attendu :**
```
NAME                        STATUS              PORTS
ie_service                  Up (healthy)        0.0.0.0:5006->5006/tcp
crud_service                Up (healthy)        0.0.0.0:5002->5002/tcp
business_service            Up (healthy)        0.0.0.0:5003->5003/tcp
appraisal_service           Up (healthy)        0.0.0.0:5005->5005/tcp
approval_service            Up (healthy)        0.0.0.0:5007->5007/tcp
notification_service        Up (healthy)        0.0.0.0:5008->5008/tcp
orchestrator_service        Up (healthy)        0.0.0.0:5004->5004/tcp
adapter_rest_service        Up (healthy)        0.0.0.0:5001->5001/tcp
web_interface_service       Up (healthy)        0.0.0.0:5000->5000/tcp
```

### Accès aux services

| Service           | URL                                  | Type      |
|-------------------|--------------------------------------|-----------|
| Web Interface     | http://localhost:5000                | HTML      |
| REST API          | http://localhost:5001/api/loan/apply | POST JSON |
| SOAP Orchestrator | http://localhost:5004/?wsdl          | WSDL/SOAP |
| Health Check      | http://localhost:5001/health         | JSON      |

### Arrêt

```bash
# Arrêter tous les conteneurs
docker-compose down

# Arrêter et supprimer les volumes
docker-compose down -v

# Supprimer les images
docker-compose down --rmi all
```

### Mode Développement (sans Docker)

```bash
# Installation Python 3.9+
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# ou : venv\Scripts\activate  # Windows

# Installer les dépendances
pip install -r requirements.txt

# Démarrer chaque service dans des terminaux séparés
python services/service_crud/service_crud.py
python services/service_business/service_business.py
python services/service_ie/service_ie.py
python services/service_appraisal/service_appraisal.py
python services/service_approval/service_approval.py
python services/service_notification/service_notification.py
python services/service_orchestrator/service_orchestrator.py  # Attendre que tous soient UP
python services/service_adapter/adapter_rest.py
python services/interface/app.py
```

---

## Utilisation

### 1. Interface Web (Recommandée)

Ouvrir **http://localhost:5000** dans le navigateur.

**Formulaire :**
```
CLIENT_ID: client-002
LOAN_AMOUNT: 350000
LOAN_DURATION: 20
PROPERTY_ADDRESS: 456 Elm St, NYC
PROPERTY_DESCRIPTION: Modern apartment
PROPERTY_SURFACE: 1400
CONSTRUCTION_YEAR: 2015
```

### 2. API REST (curl)

```bash
curl -X POST http://localhost:5001/api/loan/apply \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "client-002",
    "request_text": "CLIENT_ID: client-002\nLOAN_AMOUNT: 350000\nLOAN_DURATION: 20\nPROPERTY_ADDRESS: 456 Elm St, NYC\nPROPERTY_DESCRIPTION: Modern apartment\nPROPERTY_SURFACE: 1400\nCONSTRUCTION_YEAR: 2015"
  }'
```

### 3. Client SOAP (Python + Zeep)

```python
from zeep import Client

client = Client(wsdl='http://localhost:5004/?wsdl')
result = client.service.process_loan_request(
    client_id='client-002',
    request_text='CLIENT_ID: client-002\n...'
)
print(result)
```

---

## Endpoints & WSDL

### URLs WSDL (copier dans SoapUI)

```
http://localhost:5006/?wsdl   → IE Service
http://localhost:5002/?wsdl   → CRUD Service
http://localhost:5003/?wsdl   → Business Service
http://localhost:5005/?wsdl   → Appraisal Service
http://localhost:5007/?wsdl   → Approval Service
http://localhost:5008/?wsdl   → Notification Service
http://localhost:5004/?wsdl   → Orchestrator (Principal)
```

### Endpoint principal (API Gateway)

```
POST http://localhost:5001/api/loan/apply
Content-Type: application/json

Request:
{
  "client_id": "client-XXX",
  "request_text": "CLIENT_ID: ...\nLOAN_AMOUNT: ...\n..."
}

Response:
{
  "status": "success",
  "correlation_id": "UUID",
  "client_email": "...",
  "credit_assessment": {...},
  "property_evaluation": {...},
  "final_decision": {...}
}
```

---

## Exemples de Requêtes/Réponses

### Cas Nominal : Approbation (client-002)

**Requête POST /api/loan/apply :**
```json
{
  "client_id": "client-002",
  "request_text": "CLIENT_ID: client-002\nLOAN_AMOUNT: 300000\nLOAN_DURATION: 20\nPROPERTY_ADDRESS: 456 Elm St, NYC\nPROPERTY_DESCRIPTION: Modern apartment with view\nPROPERTY_SURFACE: 1400\nCONSTRUCTION_YEAR: 2015"
}
```

**Réponse 200 OK :**
```json
{
  "status": "success",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "client_email": "alice.smith@example.com",
  "timestamp": "2025-11-11T12:34:56Z",
  "credit_assessment": {
    "score": 800,
    "grade": "A",
    "status": "solvent",
    "explanations": {
      "credit": "✓ Excellent ! Score 800/1000, historique solide",
      "income": "✓ Capacité d'épargne: $3000/mois",
      "history": "✓ Aucun retard, dettes: $2000"
    }
  },
  "property_evaluation": {
    "estimated_value": 420000,
    "is_compliant": true,
    "reason": "Valeur estimée: $420,000. Région: NYC. Surface: 1400 m² (moyen). État: Propriété moderne (Valeur standard).",
    "evaluation_status": "COMPLETED"
  },
  "final_decision": {
    "approved": true,
    "decision": "✓ APPROUVÉE",
    "interest_rate": 3.75,
    "justification": "Profil excellent",
    "risk_level": "MOYEN",
    "justification": "Profil satisfaisant"
  }
}
```

### Cas d'Erreur : Client Non Trouvé

**Requête :**
```json
{
  "client_id": "client-999",
  "request_text": "CLIENT_ID: client-999\n..."
}
```

**Réponse 404 Not Found :**
```json
{
  "error": "Client non trouvé. Client 'client-999' non trouvé dans le système.",
  "status": "error",
  "fault_code": "Client.NotFound"
}
```

### Cas d'Erreur : Région Inconnue → Expert Review (202)

**Propriété en région non mappée :**
```json
{
  "error": "La région de la propriété n'est pas reconnue. La région 'Paris' n'est pas dans notre base. Expertise requise.",
  "status": "error",
  "fault_code": "Property.RegionNotFound"
}
```

**Réponse 202 Accepted** (traitement dépendant d'une expertise manuelle)

---

## Stratégie de Tests

### 1. Tests Unitaires (pytest)

**Fichier :** `tests/test_services.py`

```bash
# Installer pytest
pip install pytest pytest-cov

# Exécuter tous les tests
pytest tests/test_services.py -v

# Avec couverture de code
pytest tests/test_services.py --cov=services --cov-report=html
```

**Couverture testée :**
- ✓ ComputeCreditScore (formule, bornes, grades)
- ✓ DecideSolvency (seuils income/expenses, score)
- ✓ ExplanationService (messages cohérents)
- ✓ Validation clientId (pattern regex)
- ✓ Gestion erreurs (Faults)

### 2. Tests d'Intégration (Zeep)

**Fichier :** `tests/test_integration.py`

```bash
# Prérequis : services Docker actifs
docker-compose up -d

# Exécuter les tests
pytest tests/test_integration.py -v --tb=short

```

**Données de test :**

| Client     | Score       | Attendu                | Revenu | Dépenses |
|------------|-------------|------------------------|--------|----------|
| client-001 | 400         | Not Solvent            | $4000  | $3000    |
| client-002 | 800         | Solvent                | $5500  | $2500    |
| client-003 | 0 (clamped) | Not Solvent (faillite) | $3500  | $3200    |
| client-004 | 250         | Not Solvent (faillite) | $4500  | $2500    |

### 3. Tests SoapUI (Graphique)

1. Importer WSDL : `http://localhost:5004/?wsdl`
2. Auto-générer requêtes
3. Exécuter test suite
4. Asserter réponses

**Test Cases :**
- [x] VerifySolvency - Happy Path
- [x] VerifySolvency - Client Not Found
- [x] VerifySolvency - Invalid Format
- [x] Property Region Not Found
- [x] Response Structure Validation

### 4. Tests de Charge (optionnel)

```bash
# Avec Apache JMeter ou hey
hey -n 100 -c 10 http://localhost:5001/api/loan/apply
```

**Cible :** p95 < 300ms sur données in-memory

---

## SLA & QoS

### Service Level Agreement (SLA)

| Métrique                | Cible   | Notes                 |
|-------------------------|---------|-----------------------|
| **Disponibilité**       | 99%     | Heures de TD (8h-18h) |
| **Temps réponse (p50)** | < 100ms | Données in-memory     |
| **Temps réponse (p95)** | < 300ms | Pic d'utilisation     |
| **Temps réponse (p99)** | < 500ms | Cas extrêmes          |
| **Uptime cible**        | 99.5%   | Sur 1 semaine         |

### Quality of Service (QoS) - Métriques

**Logs actifs (INFO level) :**
```
[Service] timestamp - event_type - correlation_id - latency_ms
```

**Compteurs exportés :**
```bash
# Nombre d'appels par opération
[CRUD] GetClientIdentity called: 245 times

# Latences moyennes
[Orchestrator] average_latency_ms: 87.3
[Orchestrator] p95_latency_ms: 245.1
```

**Health Checks :**
```bash
curl http://localhost:5000/health     # Web Interface
curl http://localhost:5001/health     # REST Adapter
curl http://localhost:5004/?wsdl      # SOAP Orchestrator
```

### Mesures de Performance

Au shutdown des services, afficher :
```
======================== PERFORMANCE SUMMARY ========================
Orchestrator Service:
  Total Requests: 1247
  Avg Latency: 89.2ms
  p95 Latency: 256.3ms
  p99 Latency: 489.1ms
  Error Rate: 0.8%

CRUD Service:
  Total Requests: 4988 (x4 par loan request)
  Cache Hit Rate: 0% (pas de caching actuellement)

Business Service:
  Total Requests: 2494
  Score Computation Time: 1-3ms (negligible)

REST Adapter:
  HTTP Requests: 1247
  SOAP Marshalling: avg 12ms
========================================================================
```

---

## Limitations & Améliorations Futures

### Limitations actuelles

1. **Pas de persistance réelle**
   - Données clients en mémoire (dictionnaire Python)
   - Perte au redémarrage du conteneur
   - → **À faire :** PostgreSQL avec ORM (SQLAlchemy)

2. **Pas d'authentification**
   - Pas de WS-Security, pas de certificats
   - → **À faire :** WS-Security + X.509, OAuth2 pour REST

3. **Cache absent**
   - Chaque appel requête tous les services (CRUD) même si répétés
   - → **À faire :** Redis cache 5 min pour clients

4. **Pas de monitoring/observabilité**
   - Logs texte uniquement
   - → **À faire :** Prometheus métriques + Grafana + ELK stack

5. **Pas de versioning SOAP actif**
   - Namespace v1 fixé
   - → **À faire :** Support API versioning (v2 avec champs optionnels)


6. **Base de marché appraisal** simplifiée
   - 3 régions US uniquement (Boston, NYC, LA)
   - → **À faire :** Intégration API Zillow/Redfin réelle

7. **DTI/LTV** sans ajustements avancés
   - Pas de gestion auto-entrepreneur, revenus saisonniers
   - → **À faire :** Modèle ML pour scoring avancé


## Troubleshooting

### Port déjà utilisé

```bash
# Trouver le processus utilisant le port 5000
lsof -i :5000
kill -9 <PID>

# Ou utiliser un autre port dans docker-compose.yml
# "5010:5000" au lieu de "5000:5000"
```

### Services ne démarrent pas

```bash
# Vérifier les logs
docker-compose logs orchestrator_service

# Attendre plus longtemps (healthcheck timeout)
docker-compose up --wait  # Docker Compose v2.1+

# Rebuild sans cache
docker-compose build --no-cache
```

### SOAP Fault timeout

```bash
# Augmenter timeout dans orchestrator
# Environ ligne 50 de service_orchestrator.py
timeout = 60  # secondes
```

### Erreur de validation XSD

```bash
# Activer mode debug
PYTHONUNBUFFERED=1 docker-compose logs -f | grep -i "validation"
```


## License

Projet SOA - Université Paris-Saclay (2025)

**Auteur :** Sarrah Harrouche & Boualam Mokeddem & Souhil Ouchene 
**Date :** Novembre 2025

---

**Prêt ? Exécutez :** `docker-compose up -d && sleep 5 && curl http://localhost:5000`
