from flask import Flask, render_template, request, redirect
import sqlite3

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect('inventory.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    conn = get_db_connection()
    items = conn.execute('SELECT * FROM items').fetchall()
    conn.close()
    return render_template('index.html', items=items)

@app.route('/add', methods=['GET', 'POST'])
def add_item():
    if request.method == 'POST':
        name = request.form['name']
        unit = request.form['unit']
        stock = request.form['stock']

        conn = get_db_connection()
        conn.execute('INSERT INTO items (name, unit, stock) VALUES (?, ?, ?)',
                     (name, unit, stock))
        conn.commit()
        conn.close()

        return redirect('/')
    return render_template('add_item.html')

if __name__ == '__main__':
    app.run(debug=True)
