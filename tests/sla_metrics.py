# sla_metrics.py
import requests
import time
import statistics
from datetime import datetime

def test_sla(url="http://localhost:5001", duration_minutes=5, verbose=False):
    """Test SLA pendant X minutes"""
    
    print(f"🔍 Test SLA en cours ({duration_minutes} minutes)...\n")
    
    times = []
    errors = 0
    total_requests = 0
    start_time = time.time()
    end_time = start_time + (duration_minutes * 60)
    
    payload = {
        "client_id": "client-002",
        "request_text": "CLIENT_ID: client-002\nLOAN_AMOUNT: 300000\nLOAN_DURATION: 20\nPROPERTY_ADDRESS: 456 Elm St, NYC\nPROPERTY_DESCRIPTION: Test\nPROPERTY_SURFACE: 1400\nCONSTRUCTION_YEAR: 2015"
    }
    
    while time.time() < end_time:
        try:
            req_start = time.time()
            resp = requests.post(f"{url}/api/loan/apply", json=payload, timeout=10)
            elapsed = (time.time() - req_start) * 1000
            
            total_requests += 1
            times.append(elapsed)
            
            if resp.status_code != 200:
                errors += 1
                if verbose:
                    print(f"❌ Erreur {resp.status_code}")
            else:
                if verbose:
                    print(f"✅ {elapsed:.1f}ms")
                    
        except requests.Timeout:
            errors += 1
            if verbose:
                print(f"⏱️ Timeout")
        except Exception as e:
            errors += 1
            if verbose:
                print(f"🔴 {str(e)[:30]}")
        
        time.sleep(1)  # 1 requête par seconde
    
    times.sort()
    
    # Calculs
    error_rate = (errors / total_requests * 100) if total_requests > 0 else 0
    availability = ((total_requests - errors) / total_requests * 100) if total_requests > 0 else 0
    
    p50 = statistics.median(times) if times else 0
    p95 = times[int(len(times) * 0.95)] if times else 0
    p99 = times[int(len(times) * 0.99)] if times else 0
    
    # Afficher résultats
    print("\n" + "="*60)
    print("📊 RÉSULTATS SLA")
    print("="*60)
    
    print("\n⏱️  LATENCE")
    print(f"  Min:     {min(times) if times else 0:.1f}ms")
    print(f"  P50:     {p50:.1f}ms  (Cible: <100ms)")
    print(f"  P95:     {p95:.1f}ms  (Cible: <300ms)")
    print(f"  P99:     {p99:.1f}ms  (Cible: <500ms)")
    print(f"  Max:     {max(times) if times else 0:.1f}ms")
    
    print("\n🎯 DISPONIBILITÉ")
    print(f"  Total Requêtes: {total_requests}")
    print(f"  Erreurs:        {errors}")
    print(f"  Taux d'erreur:  {error_rate:.2f}%    (Cible: <1%)")
    print(f"  Disponibilité:  {availability:.2f}%   (Cible: 99%)")
    
    print("\n" + "="*60)
    print("✅ Tableau pour README :\n")
    
    print("| Métrique | Cible | Observé | Status |")
    print("|----------|-------|---------|--------|")
    print(f"| P50 | <100ms | {p50:.0f}ms | {'✅' if p50 < 100 else '⚠️'} |")
    print(f"| P95 | <300ms | {p95:.0f}ms | {'✅' if p95 < 300 else '⚠️'} |")
    print(f"| P99 | <500ms | {p99:.0f}ms | {'✅' if p99 < 500 else '⚠️'} |")
    print(f"| Disponibilité | 99% | {availability:.1f}% | {'✅' if availability >= 99 else '⚠️'} |")
    print(f"| Taux erreur | <1% | {error_rate:.2f}% | {'✅' if error_rate < 1 else '⚠️'} |")

if __name__ == "__main__":
    # Test court (5 min) ou modifie la durée
    test_sla(duration_minutes=5, verbose=False)