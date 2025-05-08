from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI
import os
from dotenv import load_dotenv
from datetime import datetime
from collections import defaultdict
import re

# Load env and setup OpenAI client
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = Flask(__name__)

# Track totals: {phone: {date: dict of totals}}
user_meals = defaultdict(lambda: defaultdict(lambda: {'calories': 0, 'protein': 0, 'fat': 0, 'carbs': 0}))
# Track last entry: {phone: {date: last_meal_dict}}
last_meals = defaultdict(lambda: defaultdict(lambda: None))

@app.route("/whatsapp", methods=["POST"])
def whatsapp_reply():
    user_msg = request.form.get("Body").strip().lower()
    user_phone = request.form.get("From")
    today = datetime.now().strftime("%Y-%m-%d")

    # Clean up old days
    for date in list(user_meals[user_phone].keys()):
        if date != today:
            del user_meals[user_phone][date]
            del last_meals[user_phone][date]

    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{timestamp} | {user_phone} | {user_msg}", flush=True)

    totals = user_meals[user_phone][today]

    # ✅ Handle "/summary" command
    if user_msg == "/summary":
        reply = f"""📊 *Your Total Nutrition Today:*
🔸 Calories: {totals['calories']} kcal
💪 Protein: {totals['protein']}g
🧈 Fat: {totals['fat']}g
🍞 Carbs: {totals['carbs']}g
"""
        twilio_resp = MessagingResponse()
        twilio_resp.message(reply)
        return str(twilio_resp)

    # ✅ Handle "reset last" command
    if user_msg == "/reset-last":
        last = last_meals[user_phone][today]
        if last:
            for key in ['calories', 'protein', 'fat', 'carbs']:
                totals[key] -= last[key]
            last_meals[user_phone][today] = None

            reply = f"""✅ *Last meal removed!*

📊 *Updated Total Today:*
🔸 Calories: {totals['calories']} kcal
💪 Protein: {totals['protein']}g
🧈 Fat: {totals['fat']}g
🍞 Carbs: {totals['carbs']}g
"""
        else:
            reply = "⚠️ No meal to reset today."

        twilio_resp = MessagingResponse()
        twilio_resp.message(reply)
        return str(twilio_resp)

    # 🧠 OpenAI Nutrition Estimation
    prompt = f"""Estimate the nutritional values for this meal: {user_msg}.

Respond ONLY in this format:
Calories: ___ kcal
Protein: ___ g
Fat: ___ g
Carbs: ___ g"""

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        raw = response.choices[0].message.content.strip()

        # Extract values using regex
        cal = int(re.search(r'Calories:\s*(\d+)', raw).group(1))
        pro = int(re.search(r'Protein:\s*(\d+)', raw).group(1))
        fat = int(re.search(r'Fat:\s*(\d+)', raw).group(1))
        carb = int(re.search(r'Carbs:\s*(\d+)', raw).group(1))

        # Store last meal
        last_meals[user_phone][today] = {
            'calories': cal,
            'protein': pro,
            'fat': fat,
            'carbs': carb
        }

        # Update totals
        totals['calories'] += cal
        totals['protein'] += pro
        totals['fat'] += fat
        totals['carbs'] += carb

        reply = f"""🥗 *Nutritional Breakdown of Your Meal:*

🔸 Calories: {cal} kcal
💪 Protein: {pro}g
🧈 Fat: {fat}g
🍞 Carbs: {carb}g

📊 *Total Today:*
🔸 Calories: {totals['calories']} kcal
💪 Protein: {totals['protein']}g
🧈 Fat: {totals['fat']}g
🍞 Carbs: {totals['carbs']}g
"""

    except Exception as e:
        reply = f"❌ Error: {str(e)}"

    twilio_resp = MessagingResponse()
    twilio_resp.message(reply)
    return str(twilio_resp)

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

