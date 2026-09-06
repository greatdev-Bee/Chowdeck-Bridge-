import asyncio
import os
import re
import httpx

RAILWAY_WEBHOOK_URL = os.getenv("RAILWAY_WEBHOOK_URL", "https://chow-bot-production.up.railway.app/tweet")
STATUS_URL = os.getenv("STATUS_URL", "https://chow-bot-production.up.railway.app/status")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "").strip()

RAW_KEYS = os.getenv("TWITTER_API_KEYS", "YOUR_TWITTERAPI_KEY_HERE")
API_KEYS = [k.strip() for k in RAW_KEYS.split(",") if k.strip()]

TARGET_USER_NAME = os.getenv("TARGET_USER_NAME", "Oyinlola6464")

async def send_admin_alert(text):
    if not TELEGRAM_BOT_TOKEN or not ADMIN_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": int(ADMIN_CHAT_ID), "text": text, "parse_mode": "Markdown"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(url, json=payload)
    except Exception as e:
        print(f"Failed to send Telegram alert: {e}", flush=True)

async def main():
    url = "https://api.twitterapi.io/twitter/user/last_tweets"
    params = {"userName": TARGET_USER_NAME}
    
    key_index = 0
    print(f"📱 Cloud TwitterAPI.io Bridge active for @{TARGET_USER_NAME}...", flush=True)
    seen_tweet_ids = set()
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        while True:
            try:
                status_res = await client.get(STATUS_URL)
                if status_res.status_code == 200:
                    status_data = status_res.json()
                    if not status_data.get("active", True):
                        print("⏸️ Bot is paused by admin. Waiting 30s...", flush=True)
                        await asyncio.sleep(30)
                        continue
            except Exception:
                pass 

            if not API_KEYS or key_index >= len(API_KEYS):
                print("❌ No valid API keys available!", flush=True)
                await asyncio.sleep(60)
                continue

            current_key = API_KEYS[key_index]
            headers = {"X-API-Key": current_key}
            
            try:
                res = await client.get(url, params=params, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    tweets = data.get("tweets", [])
                    
                    if not seen_tweet_ids and tweets:
                        for tw in tweets:
                            tid = str(tw.get("id") or "")
                            if tid:
                                seen_tweet_ids.add(tid)
                        print(f"✅ Baseline locked. Tracking {len(seen_tweet_ids)} known ID(s).", flush=True)

                    for tw in tweets:
                        tid = str(tw.get("id") or "")
                        text = str(tw.get("text") or "")
                        
                        if tid and text and tid not in seen_tweet_ids:
                            seen_tweet_ids.add(tid)
                            matches = re.findall(r'\b[A-Z0-9]{4,}\b', text)
                            code = matches[0] if matches else text.strip()
                            
                            print(f"🚨 New Code Isolated [{code}] from Tweet ID {tid}", flush=True)
                            await client.post(RAILWAY_WEBHOOK_URL, json={"text": code}, timeout=10.0)
                            
                else:
                    print(f"⚠️ API Error [{res.status_code}]: {res.text}", flush=True)
                    if res.status_code in [401, 403, 429]:
                        failed_key_num = key_index + 1
                        key_index += 1
                        
                        if key_index < len(API_KEYS):
                            alert_msg = (
                                f"⚠️ *Twitter API Key #{failed_key_num} Exhausted/Invalid!*\n"
                                f"Status {res.status_code}. Rotating to key #{key_index + 1}."
                            )
                            await send_admin_alert(alert_msg)
                        else:
                            alert_msg = (
                                f"❌ *CRITICAL: All Twitter API Keys Failed!*\n"
                                f"Status {res.status_code}: {res.text}\n"
                                f"🚨 Please check your keys immediately!"
                            )
                            await send_admin_alert(alert_msg)
            except (httpx.RequestError, OSError) as e:
                print(f"Network error: {e}", flush=True)
                await asyncio.sleep(5)
            except Exception as e:
                print(f"Polling error: {e}", flush=True)

            await asyncio.sleep(7)

if __name__ == "__main__":
    asyncio.run(main())
