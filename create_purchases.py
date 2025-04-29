import json

# דוגמת נתוני רכישות שהמשתמש עשה
user_purchases = [
    {"name": "Product1", "price": 100},
    {"name": "Product2", "price": 50},
]

# שמירה לקובץ JSON
with open("user_purchases.json", "w") as file:
    json.dump(user_purchases, file)

print("הנתונים נשמרו בהצלחה ב- user_purchases.json")
