import redis
import json

def main():
    r = redis.Redis(host='everithing_manager_redis', port=6379, db=0)
    keys = r.keys("fbpromo_chat_hist:*")
    print("--- Redis Chat Histories ---")
    for key in keys:
        print(f"Key: {key.decode('utf-8')}")
        val = r.get(key)
        if val:
            try:
                hist = json.loads(val.decode('utf-8'))
                for msg in hist:
                    role = msg.get("role")
                    parts = msg.get("parts", [])
                    text = "".join(p.get("text", "") for p in parts if "text" in p)
                    func_call = [p.get("functionCall") for p in parts if "functionCall" in p]
                    func_resp = [p.get("functionResponse") for p in parts if "functionResponse" in p]
                    
                    print(f"  [{role}]: {text[:200]}")
                    if func_call:
                        print(f"    Tool Call: {func_call}")
                    if func_resp:
                        print(f"    Tool Resp: {func_resp}")
            except Exception as e:
                print(f"    Error parsing: {e}")
        print("-" * 50)

if __name__ == "__main__":
    main()
