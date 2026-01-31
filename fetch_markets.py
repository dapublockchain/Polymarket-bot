import requests
import json


def fetch_active_markets():
    # Polymarket Gamma API to get top active events
    url = "https://gamma-api.polymarket.com/events?limit=5&active=true&closed=false"

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        print(f"Found {len(data)} events.")

        for event in data:
            print(f"\nEvent: {event.get('title')}")
            markets = event.get("markets", [])
            for market in markets:
                print(f"  Market: {market.get('question')}")
                print(f"  Condition ID: {market.get('conditionId')}")
                print(f"  Token IDs: {market.get('clobTokenIds')}")

                # Just need one pair to test
                if market.get("clobTokenIds"):
                    tokens = json.loads(market.get("clobTokenIds"))
                    if len(tokens) >= 2:
                        return tokens[0], tokens[1]

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    t1, t2 = fetch_active_markets()
    print(f"\nsucccessfully found tokens: {t1}, {t2}")
