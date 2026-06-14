from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, time
import yfinance as yf
import pytz

# 1. INITIALIZE THE FLASK APP & DATABASE
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///simulator.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Encrypt user's login cookie
app.secret_key = 'cryptomutant_alpha_key_override_993'

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

class QueuedOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    operator_id = db.Column(db.Integer, db.ForeignKey('operator.id'), nullable=False)
    ticker = db.Column(db.String(10), nullable=False)
    action = db.Column(db.String(10), nullable=False) 
    quantity = db.Column(db.Float, nullable=False)
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
    if 'username' not in session:
        return redirect(url_for('login_page'))
    
    operator = Operator.query.filter_by(username=session['username']).first()
    active_positions = Position.query.filter_by(operator_id=operator.id).all()
    # NEW: Fetch queued orders for this user
    pending_orders = QueuedOrder.query.filter_by(operator_id=operator.id).all()
    
    return render_template('dashboard.html', 
                           username=operator.username, 
                           cash=operator.liquid_cash,
                           positions=active_positions,
                           queued_orders=pending_orders)


# 3-4 Clock function to determine if market is open (for UI purposes)
def is_market_open():
    # Force the clock to New York time
    ny_time = datetime.now(pytz.timezone('US/Eastern'))
    
    # Check if it is the weekend (5 = Saturday, 6 = Sunday)
    if ny_time.weekday() >= 5:
        return False
        
    # Check if the current time is between 4:00 AM and 8:00 PM EST
    market_open = time(4, 0, 0)
    market_close = time(20, 0, 0)
    
    if market_open <= ny_time.time() <= market_close:
        return True
        
    return False

# 4. API ROUTES (Authentication Logic)
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    operator = Operator.query.filter_by(username=data['username']).first()
    
    if operator and check_password_hash(operator.password_hash, data['password']):
        # THIS IS THE MAGIC: We stamp the username onto their digital wristband
        session['username'] = operator.username 
        return jsonify({"status": "success", "message": "ACCESS_GRANTED"})
    else:
        return jsonify({"status": "error", "message": "INVALID_CIPHER"}), 401

# ADD THIS NEW ROUTE TO HANDLE DISCONNECTS
@app.route('/logout')
def logout():
    session.pop('username', None) # Rips off the wristband
    return redirect(url_for('home')) # Kicks them back to the home page

@app.route('/execute_trade', methods=['POST'])
def execute_trade():
    if 'username' not in session:
        return jsonify({"status": "error", "message": "UNAUTHORIZED_NODE"}), 401

    data = request.json
    ticker = data['ticker'].upper()
    qty = float(data['quantity'])
    action = data['action'].upper() 

    operator = Operator.query.filter_by(username=session['username']).first()

    # --- THE SMART ROUTER ---
    # If the market is closed, bypass execution and send straight to the Queue
    if not is_market_open():
        new_queue = QueuedOrder(
            operator_id=operator.id,
            ticker=ticker,
            action=action,
            quantity=qty
        )
        db.session.add(new_queue)
        db.session.commit()
        return jsonify({
            "status": "success", 
            "message": f"MARKET_CLOSED: {action} ORDER PLACED IN QUEUE"
        })

    # --- STANDARD LIVE EXECUTION ---
    try:
        stock = yf.Ticker(ticker)
        current_price = stock.history(period="1d")['Close'].iloc[-1]
    except Exception as e:
        return jsonify({"status": "error", "message": "INVALID_TICKER"}), 400

    total_value = current_price * qty

    if action == 'BUY':
        if operator.liquid_cash < total_value:
            return jsonify({"status": "error", "message": "INSUFFICIENT_LIQUIDITY"}), 400
        
        operator.liquid_cash -= total_value
        position = Position.query.filter_by(operator_id=operator.id, ticker=ticker).first()
        if position:
            total_cost = (position.quantity * position.average_cost) + total_value
            position.quantity += qty
            position.average_cost = total_cost / position.quantity
        else:
            new_position = Position(operator_id=operator.id, ticker=ticker, quantity=qty, average_cost=current_price)
            db.session.add(new_position)

    elif action == 'SELL':
        position = Position.query.filter_by(operator_id=operator.id, ticker=ticker).first()
        if not position or position.quantity < qty:
            return jsonify({"status": "error", "message": "INSUFFICIENT_ASSET_QUANTITY"}), 400
        
        operator.liquid_cash += total_value
        position.quantity -= qty
        if position.quantity == 0:
            db.session.delete(position)

    new_trade = TradeLedger(
        operator_id=operator.id, ticker=ticker, action=action, 
        quantity=qty, execution_price=current_price
    )
    db.session.add(new_trade)
    db.session.commit()
    
    return jsonify({
        "status": "success", 
        "message": f"ORDER_FILLED: {action} {qty} {ticker} @ ${current_price:.2f}"
    })

@app.route('/queue_order', methods=['POST'])
def queue_order():
    if 'username' not in session:
        return jsonify({"status": "error", "message": "UNAUTHORIZED"}), 401
    
    data = request.json
    operator = Operator.query.filter_by(username=session['username']).first()
    
    new_queue = QueuedOrder(
        operator_id=operator.id,
        ticker=data['ticker'].upper(),
        action=data['action'].upper(),
        quantity=float(data['quantity'])
    )
    db.session.add(new_queue)
    db.session.commit()
    
    return jsonify({"status": "success", "message": "ORDER_QUEUED_SUCCESSFULLY"})

@app.route('/cancel_queue', methods=['POST'])
def cancel_queue():
    if 'username' not in session:
        return jsonify({"status": "error", "message": "UNAUTHORIZED"}), 401
    
    data = request.json
    order = QueuedOrder.query.get(data['queue_id'])
    
    if order and order.operator_id == Operator.query.filter_by(username=session['username']).first().id:
        db.session.delete(order)
        db.session.commit()
        return jsonify({"status": "success", "message": "ORDER_CANCELLED"})
        
    return jsonify({"status": "error", "message": "ORDER_NOT_FOUND"}), 404

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