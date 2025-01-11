import jwt
import uuid
import hashlib
import time
from urllib.parse import urlencode
import requests


def get_order_chance(access_key, secret_key, market):
    api_url = "https://api.bithumb.com"

    # Set API parameters
    param = dict(market=market)

    # Generate access token
    query = urlencode(param).encode()
    hash = hashlib.sha512()
    hash.update(query)
    query_hash = hash.hexdigest()
    payload = {
        "access_key": access_key,
        "nonce": str(uuid.uuid4()),
        "timestamp": round(time.time() * 1000),
        "query_hash": query_hash,
        "query_hash_alg": "SHA512",
    }
    jwt_token = jwt.encode(payload, secret_key)
    authorization_token = "Bearer {}".format(jwt_token)
    headers = {"Authorization": authorization_token}

    try:
        # Call API
        response = requests.get(
            api_url + "/v1/orders/chance", params=param, headers=headers
        )
        # handle to success or fail
        return response.status_code, response.json()
    except Exception as err:
        # handle exception
        return None, str(err)


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    from config import MARKET

    load_dotenv()

    bithumb_access_key = os.getenv("BITHUMB_API_KEY")
    bithumb_secret_key = os.getenv("BITHUMB_SECRET_KEY")

    get_order_chance(bithumb_access_key, bithumb_secret_key, MARKET)

    print("status_code>>>>", status_code)
    print("accounts>>>>", accounts)
