import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

from helpers import apology, login_required, lookup, usd, buysell

from flask import g

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd
app.jinja_env.filters["buysell"] = buysell

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")

# Get username for displaying in layout.html
@app.before_request
def load_user():
    if "user_id" in session:
        [query] = db.execute("SELECT username FROM users WHERE id = ?", session["user_id"])
        g.user = query["username"]


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # Calculate amounts for each of the users shareholdings
    myShareholdings = db.execute('''
    SELECT
        symbol,
        SUM(qnty * type) sharesNo
    FROM
        transactions
    WHERE
        userid = ?
    GROUP BY
        symbol
    ;''', session["user_id"])

    gt = 0
    for holding in myShareholdings:
        stocks = lookup(holding["symbol"])
        holding["name"] = stocks["name"]
        holding["price"] = stocks["price"]
        holding["total"] = stocks["price"] * holding["sharesNo"]
        gt += holding["total"]

    cash = db.execute('''SELECT cash
        FROM users WHERE id = ?;''', session["user_id"])[0]['cash']
    gt += cash

    return render_template("index.html", myShareholdings=myShareholdings, cash=cash, gt=gt)

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        symbol = request.form.get("symbol")
        qntys = request.form.get("shares")

        # Ensure the number of shares was submitted correctly
        if qntys.isdigit():
            qnty = int(qntys)
        else:
            return apology("You should give a positive integer number of shares", 400)

        # Ensure symbol was submitted
        if not symbol:
            return apology("must provide stocks symbol", 400)

        # Query IEX for stocks data with symbol
        stocks = lookup(symbol)

        # Ensusre IEX replyed correctly
        if stocks == None:
            return apology("incorrect symbol maybe", 400)

        # Check if user can afford this purchase
        cash = db.execute('''SELECT cash
        FROM users WHERE id = ?;''', session["user_id"])[0]['cash']
        if cash < qnty * stocks["price"]:
            return apology("not enough money for this purchase", 400)

        # Ready to buy

        # Recording a transaction
        db.execute('''INSERT INTO transactions (userid, type, datetime, symbol, price, qnty)
        VALUES (?, ?, ?, ?, ?, ?);''',session["user_id"], 1, datetime.now(), stocks["symbol"], stocks["price"], qnty)

        # Updating the users cash ammount
        cashLeft = cash - qnty * stocks["price"]
        db.execute('''UPDATE users
        SET cash = ?
        WHERE id = ?;''', cashLeft, session["user_id"])

        return redirect("/")


    else:
        #symb = request.form.get("symb")
        #print(symb)
        return render_template("order.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    hist = db.execute('''SELECT *
        FROM transactions
        WHERE userid = ?;''', session["user_id"])

    return render_template("history.html", hist=hist)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?",
                          request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide stocks symbol", 400)

        # Query IEX for stocks data with symbol
        stocks = lookup(request.form.get("symbol"))

        # Ensusre IEX replyed correctly
        if stocks == None:
            return apology("incorrect symbol maybe", 400)

        # Render acquired info on the quoted stocks
        return render_template("quoted.html", quote=stocks)

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensusre confirmation is submitted
        elif not request.form.get("confirmation"):
            return apology("must provide password confirmation", 400)

        # Ensure the passord and confitmation match
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("password and confirmation mismatch", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?",
                          request.form.get("username"))

        # Check if the username is not taken
        if len(rows) > 0:
            return apology("this username is taken", 400)

        # Generate the password's hash
        pswHash = generate_password_hash(request.form.get(
            "password"), method='pbkdf2:sha256', salt_length=8)

        # Add the new user to db
        db.execute('''INSERT INTO users (username, hash)
        VALUES (?, ?);''', request.form.get("username"), pswHash)

        return redirect("/login")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        symbol = request.form.get("symbol")
        qntys = request.form.get("shares")

        # Ensure the number of shares was submitted correctly
        if qntys.isdigit():
            qnty = int(qntys)
        else:
            return apology("You should give a positive integer number of shares", 400)

        # Ensure symbol was submitted
        if not symbol:
            return apology("must provide stocks symbol", 400)

        # Query IEX for stocks data with symbol
        stocks = lookup(symbol)

        # Ensusre IEX replyed correctly
        if stocks == None:
            return apology("incorrect symbol maybe", 400)

        # Check if user owns the selected stocks and calculate number of shares if any
        myShareholdings = db.execute('''
            SELECT
                symbol,
                SUM(qnty * type) sharesNo
            FROM
                transactions
            WHERE
                userid = ? AND symbol == ?
            GROUP BY
                symbol
            ;''', session["user_id"], symbol)

        if myShareholdings == []:
            return apology(f"you don't own {symbol} shares", 400)

        # Check if the user owns enough of the chosen stocks
        if qnty > myShareholdings[0]["sharesNo"]:
            return apology("you can't sell more shares than you own", 400)

        # Ready to sell

        # Recording a transaction
        db.execute('''INSERT INTO transactions (userid, type, datetime, symbol, price, qnty)
        VALUES (?, ?, ?, ?, ?, ?);''',session["user_id"], -1, datetime.now(), stocks["symbol"], stocks["price"], qnty)

        # Updating the users cash ammount
        cash = db.execute('''SELECT cash
        FROM users WHERE id = ?;''', session["user_id"])[0]['cash']
        cashLeft = cash + qnty * stocks["price"]
        db.execute('''UPDATE users
        SET cash = ?
        WHERE id = ?;''', cashLeft, session["user_id"])

        return redirect("/")


    else:
        allMyShareholdings = db.execute('''
            SELECT
                symbol,
                SUM(qnty * type) sharesNo
            FROM
                transactions
            WHERE
                userid = ?
            GROUP BY
                symbol
            ;''', session["user_id"])
        mySymbs = []
        for hold in allMyShareholdings:
            if hold["sharesNo"] > 0:
                mySymbs.append(hold["symbol"])

        return render_template("sell.html", mySymbs=mySymbs)
