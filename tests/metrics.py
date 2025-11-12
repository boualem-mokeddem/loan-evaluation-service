# metrics.py
import requests
import time
import statistics

def get_metrics(url, iterations=10):
    times = []
    errors = 0
    
    for _ in range(iterations):
        try:
            start = time.time()
            resp = requests.post(
                f"{url}/api/loan/apply",
                json={
                    "client_id": "client-002",
                    "request_text": "CLIENT_ID: client-002\nLOAN_AMOUNT: 300000\nLOAN_DURATION: 20\nPROPERTY_ADDRESS: 456 Elm St, NYC\nPROPERTY_DESCRIPTION: Test\nPROPERTY_SURFACE: 1400\nCONSTRUCTION_YEAR: 2015"
                },
                timeout=10
            )
            elapsed = (time.time() - start) * 1000
            times.append(elapsed)
            if resp.status_code != 200:
                errors += 1
        except:
            errors += 1
    
    times.sort()
    
    print(f"Response Time Distribution ({iterations} requêtes):")
    print(f"- Min: {min(times):.1f}ms")
    print(f"- Median: {statistics.median(times):.1f}ms")
    print(f"- P95: {times[int(len(times)*0.95)]:.1f}ms")
    print(f"- Max: {max(times):.1f}ms")
    print(f"- Error Rate: {errors/iterations*100:.1f}%")

if __name__ == "__main__":
    get_metrics("http://localhost:5001")