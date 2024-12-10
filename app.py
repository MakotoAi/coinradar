from dotenv import load_dotenv

load_dotenv()

from flask import Flask, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
import os
from telebot import TeleBot
from werkzeug.utils import secure_filename
from datetime import datetime


MONGODB_URI = os.environ["MONGODB_URI"]
DB_NAME = os.environ["DB_NAME"]

client = MongoClient(MONGODB_URI)
db = client[DB_NAME]

app = Flask(__name__)

app.secret_key = bytes.fromhex(os.environ['SECRET_KEY'])

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_ID = os.environ["TELEGRAM_ID"]
# TELEGRAM_BOT_TOKEN = "8187023502:AAFFOCiE0kEbbGe6ymKfddQm7FkRAT6KmGY"
# TELEGRAM_ID = "6263694482"

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('About.html')

@app.route('/contact', methods = ['GET', 'POST'])
def contact():
    if request.method == 'GET':
        return render_template('Contact.html')

    name = request.form['name']
    email = request.form['email']
    message = request.form['message']

    bot = TeleBot(TELEGRAM_BOT_TOKEN, parse_mode = 'HTML', threaded = False)
    text = f"""
Ada request artikel dari {name} {email}

Isi Pesan: {message} 
""".strip()
    print(TELEGRAM_ID)
    print(bot.get_me())
    bot.send_message(TELEGRAM_ID, text)
    flash("Pesan berhasil dikirim", 'success')
    return redirect('/contact')

@app.route('/adminpage')
def dashboard():
    return render_template('AdminPage.html')

@app.route('/fpass', methods=['GET', 'POST'])
def fpass():
    if request.method == 'POST':
        if 'email' in request.form and 'password' not in request.form:
            email = request.form['email']
            user = db.users.find_one({'email': email})

            if user:
                flash('Email ditemukan. Silakan masukkan password baru.', 'success')
                return render_template('fpass.html', email=email)  
            else:
                flash('Email tidak ditemukan. Mohon periksa alamat email Anda.', 'danger')

        elif 'password' in request.form:
            email = request.form['email']
            new_password = request.form['password']

            if not new_password:
                flash('Password baru tidak boleh kosong.', 'danger')
                return render_template('fpass.html', email=email)

            hashed_password = generate_password_hash(new_password)

            result = db.users.update_one({'email': email}, {'$set': {'password': hashed_password}})
            
            if result.modified_count > 0:
                flash('Password berhasil direset. Silakan login.', 'success')
                return redirect(url_for('login'))
            else:
                flash('Gagal memperbarui password. Silakan coba lagi.', 'danger')

    return render_template('fpass.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = db.users.find_one({'email': email})

        if user and check_password_hash(user['password'], password):
            session['email'] = email
            session['role'] = user['role']
            flash('Login successful!', 'success')
            if user['role'] == 'admin':
                return redirect(url_for('dashboard'))
            elif user['role'] == 'user':
                return redirect(url_for('home')) 
        else:
            flash('Invalid username or password.', 'danger')

    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']  
        avatar = request.form.get('avatar') 


        hashed_password = generate_password_hash(password)

        db.users.insert_one({
            'username': username,
            'email': email,
            'password': hashed_password,
            'role': role,
            'avatar': avatar
        })

        flash('Signup successful! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('role', None)
    flash('You have logged out.', 'info')
    return redirect(url_for('home'))

@app.route('/publish', methods=['GET', 'POST'])
def publish_article():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        category = request.form['category']
        
        if 'thumbnail' in request.files:
            thumbnail_file = request.files['thumbnail']
            if thumbnail_file and allowed_file(thumbnail_file.filename):
                filename = secure_filename(thumbnail_file.filename)
                thumbnail_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                thumbnail_path = f'uploads/{filename}'
            else:
                thumbnail_path = None
        else:
            thumbnail_path = None

        published_at = datetime.now()

        db.articles.insert_one({
            'title': title,
            'description': description,
            'category': category,
            'thumbnail': thumbnail_path,
            'published_at': published_at  
        })

        flash('Article published successfully!', 'success')
        return redirect(url_for('publish_article'))

    return render_template('publish.html')

def allowed_file(filename):
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

@app.route('/singlepage')
def singlepage():
    return render_template('singlepage.html')

@app.route('/articles', methods=['GET'])
def get_articles():
    articles = list(db.articles.find({}, {'_id': 0})) 
    return {'articles': articles}, 200

@app.route('/update_article/<string:title>', methods=['GET', 'POST'])
def update_article(title):
    if request.method == 'POST':
        new_title = request.form['title']
        description = request.form['description']
        category = request.form['category']
        
        db.articles.update_one(
            {'title': title},
            {'$set': {
                'title': new_title,
                'description': description,
                'category': category,
                'updated_at': datetime.now()
            }}
        )
        flash('Article updated successfully!', 'success')
        return redirect(url_for('dashboard'))

    article = db.articles.find_one({'title': title})
    return render_template('update.html', article=article)

@app.route('/delete_article/<string:title>', methods=['POST'])
def delete_article(title):
    result = db.articles.delete_one({'title': title})
    if result.deleted_count > 0:
        flash('Article deleted successfully!', 'success')
    else:
        flash('Failed to delete the article. Article not found.', 'error')
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run('0.0.0.0', port=5000, debug=True)