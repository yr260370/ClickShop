from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
from flask_sqlalchemy import SQLAlchemy 
from datetime import datetime, date, timedelta
from models import db
import pandas as pd
import os
import matplotlib.pyplot as plt
import io
from faker import Faker
import numpy as np
import requests
from bs4 import BeautifulSoup
import json
from bidi.algorithm import get_display
import arabic_reshaper
plt.rcParams['font.family'] = 'Calibri'
plt.rcParams['font.sans-serif'] = ['Arial', 'Assistant', 'Tahoma']
plt.rcParams['axes.unicode_minus'] = False
from models import User, Purchase


app = Flask(__name__)

app.secret_key = 'your_secret_key' #אבטחת נתונים
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///purchases.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)  # הרשמת האפליקציה עם ה-SQLAlchemy




@app.route('/index')
def index():
    return render_template("index.html")

@app.route('/', methods=['GET'])
def home():
    return index()  #render_template('index.html')



# יצירת נתונים מזויפים עבור רכישות
fake = Faker('he_IL')  # עברית
Faker.seed(0)

# יצירת נתונים דמוי רכישות עם numpy
def generate_fake_data(num_entries=10):
    np.random.seed(0)
     # נתונים אקראיים
    products = np.random.choice(['מוצר A', 'מוצר B', 'מוצר C', 'מוצר D', 'מוצר E'], size=num_entries)
    quantities = np.random.randint(1, 6, size=num_entries)
    prices = np.random.randint(10, 101, size=num_entries)
    categories = np.random.choice(['קטגוריה 1', 'קטגוריה 2', 'קטגוריה 3'], size=num_entries)
    # יצירת תאריכים אקראיים
    start_date = datetime.now() - timedelta(days=365)
    dates = [start_date + timedelta(days=np.random.randint(0, 365)) for _ in range(num_entries)]
    # חישוב סך הוצאה
    total_costs = quantities * prices    
    # יצירת DataFrame
    df = pd.DataFrame({
        'שם מוצר': products,
        'כמות': quantities,
        'מחיר': prices,
        'קטגוריה': categories,
        'תאריך': dates,
        'סך הוצאה': total_costs
    })    
    return df
# יצירת נתונים עם numpy
demo_df = generate_fake_data(10)
demo_df['תאריך'] = pd.to_datetime(demo_df['תאריך'])
demo_df['סך הוצאה'] = demo_df['כמות'] * demo_df['מחיר']  # חישוב מחדש של סך ההוצאה


@app.route('/demoProfile')
def demo_profile():
    return render_template('demo_profile.html', purchases=demo_df.to_dict(orient='records'))



# הרשמה
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # מקבלת נתונים מהטופס
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        # בדיקה אם האימייל קיים במערכת
        if User.query.filter_by(email=email).first():
            return render_template('register.html', error="אימייל זה כבר קיים במערכת!", email=email)
        # אימות סיסמאות
        if password != confirm_password:
            return render_template('register.html', error="הסיסמאות לא תואמות!", email=email)
        # יצירת משתמש חדש
        newUser = User(username=username, email=email, password=password)
        db.session.add(newUser)
        db.session.commit()
        # עדכון ה-session לאחר ההרשמה 
        session['user_email'] = email
        session['user_id'] = newUser.id
        return redirect(url_for('profile'))
    email = request.args.get('email', '')
    return render_template('register.html', email=email)

# התחברות
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email, password=password).first()
        if user:
            session['user_email'] = email  # שומר את המשתמש המחובר
            session['user_id'] = user.id
            return redirect(url_for('profile'))
        else:
            return render_template('login.html', error="אחד או יותר מהפרטים שהוכנסו שגוי!", email=email)       
    return render_template('login.html')

# אזור אישי
@app.route('/profile')
def profile():
    email = session.get('user_email')  # השתמש ב-session כדי לשלוף את האימייל של המשתמש המחובר
    if not email:
        return redirect(url_for('login'))  # אם אין אימייל ב-session, הפנה להתחברות
    user = User.query.filter_by(email=email).first()
    if not user:
        return redirect(url_for('login'))
    purchases = Purchase.query.filter_by(user_id=user.id).all()
    return render_template('profile.html', user=user, purchases=purchases)

# מחיקת רכישות
@app.route('/delete_purchase/<int:purchase_id>', methods=['POST'])
def delete_purchase(purchase_id):
    email = session.get('user_email')
    if not email:
        return redirect(url_for('login'))
    purchase = Purchase.query.get(purchase_id)
    if purchase:
        db.session.delete(purchase)
        db.session.commit()
    return redirect(url_for('profile'))



# חיפוש בהיסטוירת רכישות
@app.route('/profile/<start_date>/<end_date>')
def profile_by_date(start_date, end_date):
    email = session.get('user_email')
    if not email:
        return redirect(url_for('login'))
    user = User.query.filter_by(email=email).first()
    if not user:
        return redirect(url_for('login'))
    # ניסיון להמיר את התאריכים למבנה datetime
    try:
        start = datetime.strptime(start_date, "%d-%m-%Y").date()
        end = datetime.strptime(end_date, "%d-%m-%Y").date()
    except ValueError:
        return render_template('profile.html', user=user, purchases=[], error="פורמט תאריכים לא תקין!")
    # סינון רכישות לפי טווח התאריכים
    purchases = Purchase.query.filter(
        Purchase.user_id == user.id,
        Purchase.date >= start,
        Purchase.date <= end
    ).all()
    return render_template('profile.html', user=user, purchases=purchases)


# הוספת רכישה
@app.route('/add', methods=['GET', 'POST'])
def add_purchase():
    user_email = session.get('user_email')
    user = User.query.filter_by(email=user_email).first()
    if not user:
        return render_template("profile.html", error="משתמש לא קיים!")
    if request.method == 'POST':
        name = request.form['name']
        quantity = int(request.form['quantity'])
        price = float(request.form['price'])
        category = request.form['category']
        date_str = request.form['date']
        purchase_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        new_purchase = Purchase(name=name, quantity=quantity, price=price, category=category, date=purchase_date, user_id=user.id)
        db.session.add(new_purchase)
        db.session.commit()
        return redirect(url_for('profile', user_email=user.email))
    current_date = date.today().strftime('%Y-%m-%d')
    return render_template('add_purchase.html', user=user, current_date=current_date)

# התנתקות
@app.route('/logout')
def logout():
    session.pop('user_email', None)  # הסרת המידע של המשתמש מה-session
    return redirect(url_for('home'))  # הפניה לדף הבית או לדף אחר


# גיבוי נתונים- קובץ CSV
@app.route('/saveData')
def save_data():
    email = session.get('user_email')
    if not email:
        return redirect(url_for('login'))

    user = User.query.filter_by(email=email).first()
    purchases = Purchase.query.filter_by(user_id=user.id).all()

    data = [{
        'שם מוצר': p.name,
        'כמות': p.quantity,
        'מחיר': p.price,
        'קטגוריה': p.category,
        'תאריך': p.date.strftime('%Y-%m-%d')
    } for p in purchases]

    df = pd.DataFrame(data)

    if not os.path.exists('backups'):
        os.makedirs('backups')

    file_path = f'backups/{user.username}_purchases.csv'
    df.to_csv(file_path, index=False, encoding='utf-8-sig')

    flash(f"הקובץ נשמר בהצלחה בשם: {file_path}", 'success')  # זו ההודעה
    return redirect(url_for('profile'))


# הורדת הקובץ
@app.route('/downloadData')
def download_data():
    email = session.get('user_email')
    if not email:
        return redirect(url_for('login'))
    user = User.query.filter_by(email=email).first()
    file_path = f'backups/{user.username}_purchases.csv'
    if not os.path.exists(file_path):
        flash("לא קיימת גיבוי להורדה. אנא בצע/י גיבוי קודם.", 'error')
        return redirect(url_for('profile'))
    return send_file(file_path, as_attachment=True)


# יצירת dataFrame
# גרף אחד בצורת עוגה לפי קטגוריה
@app.route('/graph1')
def graph1():
    return render_template("graph_template.html", title="התפלגות לפי קטגוריה", endpoint="graph1_image")
@app.route('/graph1_image')
def graph1_image():
    email = session.get('user_email')
    if not email:
        return redirect(url_for('login'))
    user = User.query.filter_by(email=email).first()
    if not user:
        return redirect(url_for('login'))
    purchases = Purchase.query.filter_by(user_id=user.id).all()
    data = [{
        'שם מוצר': p.name,
        'כמות': p.quantity,
        'מחיר': p.price,
        'קטגוריה': p.category,
        'תאריך': p.date
    } for p in purchases]    
    df = pd.DataFrame(data)
    df['סך הוצאה'] = df['כמות'] * df['מחיר']
    category_totals = df.groupby('קטגוריה')['סך הוצאה'].sum()
    category_totals.index = [get_display(arabic_reshaper.reshape(cat)) for cat in category_totals.index]
    # הגדרות תמיכה בעברית
    plt.rcParams['axes.unicode_minus'] = False
    plt.rcParams['font.family'] = 'Calibri' 
    colors = ['#12DBD8', '#56EDF5', '#41F284', '#34d0b6', '#41B2F2']
    fig, ax = plt.subplots()
    category_totals.plot(
        kind='pie',
        autopct='%1.1f%%',
        colors=colors,
        startangle=90,
        ax=ax
    )    
    ax.set_ylabel('')
    ax.set_title(get_display(arabic_reshaper.reshape('התפלגות הוצאות לפי קטגוריה')))
    plt.tight_layout() 
    img = io.BytesIO()
    plt.savefig(img, format='png', bbox_inches='tight')
    img.seek(0)
    plt.close()
    return send_file(img, mimetype='image/png')



# גרף שני עמודות לפי ממוצע חודשים
@app.route('/graph2')
def graph2():
    return render_template("graph_template.html", title="ממוצע הוצאות לפי חודש", endpoint="graph2_image")
@app.route('/graph2_image')
def graph2_image():
    email = session.get('user_email')
    if not email:
        return redirect(url_for('login'))
    user = User.query.filter_by(email=email).first()
    purchases = Purchase.query.filter_by(user_id=user.id).all()
    data = [{
        'date': p.date,
        'total': p.quantity * p.price
    } for p in purchases]
    df = pd.DataFrame(data)
    df['month'] = pd.to_datetime(df['date']).dt.to_period('M')
    monthly_avg = df.groupby('month')['total'].mean()
    # יצירת הגרף
    fig, ax = plt.subplots()
    bar_colors = ['#12DBD8', '#41F2C0', '#56EDF5', '#41F284', '#34d0b6']
    monthly_avg.plot(kind='bar', color=bar_colors[:len(monthly_avg)], ax=ax)
    # הגדרת פונטים קליברי עם כיוון RTL
    plt.rcParams['axes.unicode_minus'] = False
    plt.rcParams['font.family'] = 'Calibri'
    plt.rcParams['axes.unicode_minus'] = False
    ax.set_title(get_display(arabic_reshaper.reshape('ממוצע הוצאות חודשי')), fontsize=14, fontweight='bold')
    ax.set_ylabel(get_display(arabic_reshaper.reshape('ש״ח')), fontsize=12)
    ax.set_xlabel(get_display(arabic_reshaper.reshape('חודש')), fontsize=12)
    # הגדרת כיוון RTL
    for label in ax.get_xticklabels():
        label.set_rotation(45)
        label.set_horizontalalignment('right')  # כיוון כותרות הצירים
    for label in ax.get_yticklabels():
        label.set_horizontalalignment('right')  # כיוון כותרות הצירים
    # סידור הרווחים בתמונה
    plt.tight_layout()
    # שמירת התמונה לקובץ בזיכרון
    img = io.BytesIO()
    plt.savefig(img, format='png', bbox_inches='tight')
    img.seek(0)
    plt.close()
    # שליחה ללקוח
    return send_file(img, mimetype='image/png')

 
 

@app.route('/comparePrices')
def compare_prices():
    with open('templates/store.html', encoding='utf-8') as f:
        content = f.read()
    soup = BeautifulSoup(content, 'lxml')
    products = []
    items = soup.select('li')
    for item in items:
        name = item.select_one('.product-name').text.strip()
        price = float(item.select_one('.price').text.strip())
        products.append({'name': name, 'price': price})
    return render_template('compare_prices.html', store_products=products)



# הראוט שמטפל בייעול הקניות
@app.route('/optimize-shopping', methods=['GET', 'POST'])
def optimize_shopping():
    if request.method == 'POST':
        # שליחת בקשה לאתר
        response = requests.get("https://www.example.com/products")  # הכנס כאן את כתובת האתר שלך
        if response.status_code == 200:
            page_content = response.text
            soup = BeautifulSoup(page_content, 'html.parser')
            # חיפוש מוצרים והמחירים בעזרת BeautifulSoup
            products = soup.find_all('div', class_='product')  # שים לב לשנות את הסלקטור בהתאם למבנה האתר שלך
            products_data = []
            for product in products:
                product_name = product.find('h2').text  # הכנס את הסלקטור הנכון
                product_price = product.find('span', class_='price').text  # הכנס את הסלקטור הנכון
                products_data.append({'name': product_name, 'price': product_price})
            # הצגת המוצרים והמחירים
            return render_template('result.html', products=products_data)
        else:
            return "הייתה בעיה בקבלת נתונים מהחנות."
    return render_template('check_prices.html')



# Route להצגת דף הייעול
@app.route('/shopping_optimization')
def shopping_optimization():
    # כאן תוכל להוסיף את הקוד שלך לקרוא את המוצרים ולחפש את המחירים
    # דוגמה לאתר חנות אינטרנטית
    url = 'https://ksp.co.il/web/'
    response = requests.get(url)
    # אם הבקשה עברה בהצלחה
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        # דוגמה לחילוץ פרטי המוצרים והמחירים
        products = []
        for product in soup.find_all('div', class_='product'):  # תלוי במבנה האתר
            name = product.find('h3').text
            price = product.find('span', class_='price').text
            # השוואת מחירים - כאן עליך להוסיף את הקוד להשוואה עם המחירים הקודמים של המשתמש
            # בהנחה שאתה מחפש מחירים זולים יותר
            products.append({'name': name, 'price': price})
        return render_template('shopping_optimization.html', products=products)
    else:
        return "Error: Unable to fetch the page."



@app.route("/check_prices", methods=["GET", "POST"])
def check_prices():
    if request.method == "POST":
        product_name = request.form["product_name"]
        purchase_price = float(request.form["purchase_price"])
        product_url = request.form["product_url"]
        # שליחת בקשת GET לאתר החנות
        response = requests.get(product_url)
        soup = BeautifulSoup(response.text, "html.parser")
        # חילוץ המחיר מהדף (בהנחה שהוא תחת קלאס בשם 'price')
        price_element = soup.find(class_="price")
        if price_element:
            store_price = float(price_element.text.replace("₪", "").strip())
        else:
            store_price = None
        # 🗂️ שלב חדש: קריאת רכישות קודמות מה-JSON
        try:
            with open("user_purchases.json", "r") as file:
                user_purchases = json.load(file)
        except FileNotFoundError:
            user_purchases = []
        previous_price = None
        for item in user_purchases:
            if item["name"].lower() == product_name.lower():
                previous_price = item["price"]
                break
        return render_template("result.html",
                               product_name=product_name,
                               purchase_price=purchase_price,
                               store_price=store_price,
                               previous_price=previous_price)
    return render_template("check_prices.html")




if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    app.run(debug=True)

