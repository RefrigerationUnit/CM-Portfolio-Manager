from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

# 1. INITIALIZE THE FLASK APP & DATABASE
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///simulator.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# 2. DATABASE MODELS
class Operator(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    liquid_cash = db.Column(db.Float, default=100000.0) 

class Position(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    operator_id = db.Column(db.Integer, db.ForeignKey('operator.id'), nullable=False)
    ticker = db.Column(db.String(10), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    average_cost = db.Column(db.Float, nullable=False)

class TradeLedger(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    operator_id = db.Column(db.Integer, db.ForeignKey('operator.id'), nullable=False)
    ticker = db.Column(db.String(10), nullable=False)
    action = db.Column(db.String(10), nullable=False) 
    quantity = db.Column(db.Float, nullable=False)
    execution_price = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# 3. PAGE RENDERING ROUTES (HTML)
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login_page')
def login_page():
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

# 4. API ROUTES (Authentication Logic)
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    operator = Operator.query.filter_by(username=data['username']).first()
    
    if operator and check_password_hash(operator.password_hash, data['password']):
        return jsonify({"status": "success", "message": "ACCESS_GRANTED"})
    else:
        return jsonify({"status": "error", "message": "INVALID_CIPHER"}), 401

@app.route('/change_password', methods=['POST'])
def change_password():
    data = request.json
    operator = Operator.query.filter_by(username=data['username']).first()
    
    if operator and check_password_hash(operator.password_hash, data['old_password']):
        operator.password_hash = generate_password_hash(data['new_password'])
        db.session.commit()
        return jsonify({"status": "success", "message": "CIPHER_UPDATED"})
    else:
        return jsonify({"status": "error", "message": "OLD_CIPHER_INCORRECT"}), 401

# 5. DATABASE INITIALIZATION SCRIPT
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        if Operator.query.first() is None:
            initial_operator_ciphers = {
                "OP_Leovergas": "RaquelLerma420", 
                "OP_FDP": "LeComoElRaboABezos",       
                "OP_Joto": "Temp3",      
                "OP_Danal Semens": "RealEstateMaxxing69",
                "OP_El Guishe": "Pollas69420",
                "OP_Full Smurf": "Drogaaaa",
                "OP_Carlos": "GuillemGuillem",
                "OP_Amego de Fabio": "AmigoDeFabio69",
                "OP_Rock Cock": "Barcelona",
                "OP_Franco": "ElMolinoDelPecado69",
                "OP_Paburo": "VanessaLaQueNoDejaChotaConCabesa69",
                "OP_Kike": "KikerCasillas69",
                "OP_NegroWhatsapp": "NegroGordo69"
            }
            
            for username, original_pw in initial_operator_ciphers.items():
                hashed_pw = generate_password_hash(original_pw)
                new_op = Operator(username=username, password_hash=hashed_pw)
                db.session.add(new_op)
                
            db.session.commit()
            print("SYSTEM_DB_INITIALIZED: 13 Operators deployed.")
            
    app.run(debug=True)