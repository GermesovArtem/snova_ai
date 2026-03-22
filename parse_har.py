import json
from urllib.parse import urlparse

har_path = r'c:\Users\Пользователь\.gemini\antigravity\scratch\telegram_bot\backend\bananix.ai.har'

def analyze_har():
    with open(har_path, 'r', encoding='utf-8') as f:
        har_data = json.load(f)
        
    entries = har_data.get('log', {}).get('entries', [])
    print(f"Total requests in HAR: {len(entries)}")
    
    api_requests = []
    
    for entry in entries:
        req = entry.get('request', {})
        res = entry.get('response', {})
        url = req.get('url', '')
        method = req.get('method', '')
        status = res.get('status', 0)
        mime = res.get('content', {}).get('mimeType', '')
        
        parsed = urlparse(url)
        path = parsed.path
        
        # Filter mostly for API requests (json, auth, specific paths)
        if 'json' in mime or 'api' in path or method in ['POST', 'PUT', 'DELETE'] or \
           ('bananix.ai' in parsed.netloc and not path.endswith('.png|jpg|css|js|woff2|svg')):
            
            req_data = ""
            if req.get('postData'):
                req_data = req['postData'].get('text', '')[:100] + "..."
            
            res_data = res.get('content', {}).get('text', '')[:200]
            
            api_requests.append({
                'method': method,
                'url': url,
                'status': status,
                'request_snippet': req_data,
                'response_snippet': res_data
            })
            
    # Deduplicate by URL and Method
    seen = set()
    unique_apis = []
    for r in api_requests:
        key = (r['method'], r['url'].split('?')[0])
        if key not in seen:
            seen.add(key)
            unique_apis.append(r)
            
    print("\n--- Unique API Endpoints Discovered ---\n")
    for r in unique_apis[:50]:
        print(f"[{r['method']}] {r['url']}")
        if r['request_snippet']:
            print(f"  Req Body: {r['request_snippet']}")
        if r['response_snippet']:
            print(f"  Res Body: {r['response_snippet'].replace(chr(10), ' ')}")
        print()

if __name__ == '__main__':
    analyze_har()
