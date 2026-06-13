# admin_override.py
from app import app, db, Operator
from werkzeug.security import generate_password_hash

def force_cipher_reset(target_operator, original_password):
    with app.app_context():
        # 1. Find the locked-out operator
        operator = Operator.query.filter_by(username=target_operator).first()
        
        if operator:
            # 2. Hash their original default password
            new_hash = generate_password_hash(original_password)
            
            # 3. Overwrite the forgotten password in the database
            operator.password_hash = new_hash
            db.session.commit()
            print(f"SUCCESS: System override complete for {target_operator}.")
        else:
            print("ERROR: Operator node not found.")

# You manually trigger this when a friend is locked out:
force_cipher_reset("OP_Carlos", "Coooom34")

from flask import Flask, render_template, request, jsonify # Updated imports

# ... [Your app config and db.Model classes stay here] ...

# --- PAGE RENDERING ROUTES ---

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login_page')
def login_page():
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

# ... [Your @app.route('/login', methods=['POST']) goes here] ...