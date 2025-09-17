import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json
import requests
from dotenv import load_dotenv  # Add this import
import os

# Load .env file
load_dotenv()

# ----------------------------
# CONFIGURATION
# ----------------------------
GOOGLE_SHEET_NAME = "TFSA Info"
SHEET_TAB_NAME = "Tab1"

# Read secrets
BOT_TOKEN = os.environ['BOT_TOKEN']
CHAT_ID = os.environ['CHAT_ID']
SERVICE_ACCOUNT_JSON = os.environ['SERVICE_ACCOUNT_JSON']
SERVICE_ACCOUNT_FILE = "service_account.json"

# Save service account JSON to file for gspread
with open("service_account.json", "w") as f:
    f.write(SERVICE_ACCOUNT_JSON)

# ----------------------------
# CONNECT TO GOOGLE SHEETS
# ----------------------------
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scope)
client = gspread.authorize(creds)
sheet = client.open(GOOGLE_SHEET_NAME).worksheet(SHEET_TAB_NAME)

# Load portfolio data
WATCHED_STOCKS = ["VDY.TO", "ENB.TO", "NVDA", "DOL.TO"]
DIP_THRESHOLD = 0.015  # 1.5% dip
YESTERDAY_FILE = "yesterday.json"

data = sheet.get_all_records()
df_full = pd.DataFrame(data)

# ----------------------------
# CALCULATE TOTAL TFSA VALUE
# ----------------------------
if not {'Market Value'}.issubset(df_full.columns):
    raise ValueError("Your Google Sheet must have a 'Market Value' column")

total_value = df_full['Market Value'].sum()

# ----------------------------
# SAVE DAILY CHANGE
# ----------------------------
try:
    with open(YESTERDAY_FILE, "r") as f:
        yesterday_total = json.load(f).get("total_value", 0)
except FileNotFoundError:
    yesterday_total = total_value  # first run

daily_change = total_value - yesterday_total

# Save today's total for tomorrow
with open(YESTERDAY_FILE, "w") as f:
    json.dump({"total_value": total_value}, f)

# ----------------------------
# FILTER WATCHED STOCKS
# ----------------------------
df_watch = df_full[df_full['Symbol'].isin(WATCHED_STOCKS)]

# ----------------------------
# FORMAT TELEGRAM MESSAGE
# ----------------------------
message_lines = [f"📊 TFSA Total: ${total_value:,.2f} ({daily_change:+,.2f} today) \n"]

for _, row in df_watch.iterrows():
    ticker = row['Symbol']
    shares = row['Quantity']
    last_price = row['Price']
    market_value = row['Market Value']
    cost_basis = row['Average Cost']
    pct_change = row['Change Today %']

    gain = market_value - (cost_basis * shares)

    message_lines.append(
        f"{ticker}: Price ${last_price:.2f}, Value ${market_value:.2f}, P&L ${gain:.2f} \n"
    )

    if pct_change <= -DIP_THRESHOLD*100:
        message_lines.append(f"⚠️ {ticker} dipped {pct_change:.2f}% today!")

final_message = "\n".join(message_lines)

# ----------------------------
# SEND TELEGRAM MESSAGE
# ----------------------------
response = requests.get(
    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
    params={
        "chat_id": CHAT_ID,
        "text": final_message
    }
)

print("------ DAILY TFSA & STOCK UPDATE (Cash Excluded) ------")
print(final_message)
print("--------------------------------------")
print(response.json())  # confirm it was sent
