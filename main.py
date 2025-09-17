import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json
import requests

# ----------------------------
# CONFIGURATION
# ----------------------------
GOOGLE_SHEET_NAME = "TFSA Info"
SHEET_TAB_NAME = "Tab1"
SERVICE_ACCOUNT_FILE = "service_account.json"

WATCHED_STOCKS = ["NVDA", "VDY.TO"]
DIP_THRESHOLD = 0.015  # 1.5% dip
YESTERDAY_FILE = "yesterday.json"

# ----------------------------
# TELEGRAM SETTINGS
# ----------------------------
BOT_TOKEN = "7978179333:AAEqq6uH7UTTvZ-o_dGmIq52sTf9k66XJSc"
CHAT_ID = "6816186347"

# ----------------------------
# CONNECT TO GOOGLE SHEETS
# ----------------------------
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scope)
client = gspread.authorize(creds)

sheet = client.open(GOOGLE_SHEET_NAME).worksheet(SHEET_TAB_NAME)
data = sheet.get_all_records()
df_full = pd.DataFrame(data)

# ----------------------------
# CALCULATE TOTAL TFSA VALUE (ALL HOLDINGS)
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

message_lines = [f"TFSA Total Value: ${total_value:,.2f} ({daily_change:+,.2f} today)"]

for _, row in df_watch.iterrows():
    ticker = row['Symbol']
    shares = row['Quantity']
    last_price = row['Price']
    market_value = row['Market Value']
    cost_basis = row['Average Cost']
    pct_change = row['Change Today %'] / 100  # convert % to decimal

    gain = market_value - (cost_basis * shares)

    message_lines.append(
        f"{ticker}: {shares} shares, Price ${last_price:.2f}, Value ${market_value:.2f}, P&L ${gain:.2f}"
    )

    if pct_change <= -DIP_THRESHOLD:
        message_lines.append(f"⚠️ {ticker} dipped {pct_change*100:.2f}% today!")

# ----------------------------
# SEND TELEGRAM MESSAGE
# ----------------------------
final_message = "\n".join(message_lines)
print("------ DAILY TFSA & STOCK UPDATE ------")
print(final_message)
print("--------------------------------------")

response = requests.get(
    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
    params={
        "chat_id": CHAT_ID,
        "text": final_message
    }
)
print(response.json())  # confirm it was sent
