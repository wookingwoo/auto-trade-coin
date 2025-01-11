import jwt
import uuid
import time
import requests


def get_accounts(access_key, secret_key):
    apiUrl = "https://api.bithumb.com"

    # Generate access token
    payload = {
        "access_key": access_key,
        "nonce": str(uuid.uuid4()),
        "timestamp": round(time.time() * 1000),
    }
    jwt_token = jwt.encode(payload, secret_key)
    authorization_token = "Bearer {}".format(jwt_token)
    headers = {"Authorization": authorization_token}

    try:
        # Call API
        response = requests.get(apiUrl + "/v1/accounts", headers=headers)
        # handle to success or fail
        return response.status_code, response.json()
    except Exception as err:
        # handle exception
        print(err)


def get_simbol_accounts(bithumb_access_key, bithumb_secret_key, simbol):
    status_code, accounts = get_accounts(bithumb_access_key, bithumb_secret_key)
    if status_code == 200:
        return [account for account in accounts if account["currency"] == simbol]
    return []


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    from config import SIMBOL

    load_dotenv()

    bithumb_access_key = os.getenv("BITHUMB_API_KEY")
    bithumb_secret_key = os.getenv("BITHUMB_SECRET_KEY")

    status_code, accounts = get_accounts(bithumb_access_key, bithumb_secret_key)

    print("status_code>>>>", status_code)
    print("accounts>>>>", accounts)

    simbol_accounts = get_simbol_accounts(
        bithumb_access_key, bithumb_secret_key, SIMBOL
    )
    print(f"{SIMBOL} accounts>>>>", simbol_accounts)
