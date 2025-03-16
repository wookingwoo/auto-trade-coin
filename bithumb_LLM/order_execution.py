import jwt
import uuid
import hashlib
import time
import requests
import json
from urllib.parse import urlencode


def execute_order(api_key, secret_key, market, side, volume, price, ord_type="limit"):
    """
    Executes an order on the Bithumb exchange.
    """
    api_url = "https://api.bithumb.com"

    # Set API parameters
    request_body = {
        "market": market,
        "side": side,
        "volume": volume,
        "price": price,
        "ord_type": ord_type,
    }

    # Generate access token
    query = urlencode(request_body).encode()
    hash = hashlib.sha512()
    hash.update(query)
    query_hash = hash.hexdigest()
    payload = {
        "access_key": api_key,
        "nonce": str(uuid.uuid4()),
        "timestamp": round(time.time() * 1000),
        "query_hash": query_hash,
        "query_hash_alg": "SHA512",
    }
    jwt_token = jwt.encode(payload, secret_key)
    authorization_token = "Bearer {}".format(jwt_token)
    headers = {"Authorization": authorization_token, "Content-Type": "application/json"}

    try:
        # Call API
        response = requests.post(
            api_url + "/v1/orders", data=json.dumps(request_body), headers=headers
        )
        # Handle success or failure
        print(response.status_code)
        print(response.json())
    except Exception as err:
        # Handle exception
        print(err)
