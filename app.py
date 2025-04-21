from flask import Flask, render_template, request, redirect, session, url_for, flash
from datetime import datetime
import psycopg2
import os
from werkzeug.security import check_password_hash
from dotenv import load_dotenv


load_dotenv()  # ← .env ファイルを読み込む

app = Flask(__name__)
# Flask設定に使う
app.secret_key = os.getenv('SECRET_KEY')

# DB接続用
DATABASE_URL = os.getenv('DATABASE_URL')

def login_required(f):
    from functools import wraps
    @wraps(f)
    def wrapped(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapped

def get_db_connection():
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    return conn

@app.route('/')
def index():
    return redirect('/dashboard')

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_item():
    if request.method == 'POST':
        name = request.form['name']
        unit = request.form['unit']
        stock = int(request.form['stock'])

        # PostgreSQL用の書き方に修正
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            'INSERT INTO items (name, unit, stock) VALUES (%s, %s, %s)',
            (name, unit, stock)
        )
        conn.commit()
        cur.close()
        conn.close()

        flash(f'✅ 商品「{name}」を追加しました。')
        return redirect(url_for('stock'))

    return render_template('add_item.html')

@app.route('/add_usage', methods=['GET', 'POST'])
@login_required
def add_usage():
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        item_id = request.form['item_id']
        usage_date = request.form['usage_date']
        quantity = int(request.form['quantity'])
        usage_note = request.form['usage_note']

        # 現在の在庫数を取得
        cur.execute('SELECT stock FROM items WHERE id = %s', (item_id,))
        current_stock = cur.fetchone()[0]

        # 在庫不足チェック
        if quantity > current_stock:
            cur.execute('SELECT * FROM items')
            items = cur.fetchall()
            cur.close()
            conn.close()
            flash(f'⚠️ 在庫不足です（現在の在庫: {current_stock}）', 'error')
            return render_template('add_usage.html', items=items)

        # 使用情報を追加
        cur.execute('''
            INSERT INTO usages (item_id, usage_date, quantity, usage_note)
            VALUES (%s, %s, %s, %s)
        ''', (item_id, usage_date, quantity, usage_note))

        # 在庫を減らす
        cur.execute('''
            UPDATE items SET stock = stock - %s
            WHERE id = %s
        ''', (quantity, item_id))

        conn.commit()
        cur.close()
        conn.close()

        flash('✅ 使用情報を追加しました。')
        return redirect(url_for('stock'))

    # GET時：商品一覧を表示
    cur.execute('SELECT * FROM items')
    items = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('add_usage.html', items=items)


@app.route('/add_purchase', methods=['GET', 'POST'])
@login_required
def add_purchase():
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        item_id = request.form['item_id']
        purchase_date = request.form['purchase_date']
        quantity = int(request.form['quantity'])
        unit_price = float(request.form['unit_price']) if request.form['unit_price'] else None
        supplier = request.form['supplier']

        # purchases に追加
        cur.execute('''
            INSERT INTO purchases (item_id, purchase_date, quantity, unit_price, supplier)
            VALUES (%s, %s, %s, %s, %s)
        ''', (item_id, purchase_date, quantity, unit_price, supplier))

        # 在庫を更新
        cur.execute('''
            UPDATE items SET stock = stock + %s
            WHERE id = %s
        ''', (quantity, item_id))

        conn.commit()
        cur.close()
        conn.close()

        flash('✅ 仕入れを追加しました。')
        return redirect(url_for('stock'))

    # GETメソッドの場合
    cur.execute('SELECT * FROM items')
    items = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('add_purchase.html', items=items)

@app.route('/stock')
@login_required
def stock():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM items')
    items = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('stock.html', items=items)


@@app.route('/history', methods=['GET', 'POST'])
@login_required
def history():
    conn = get_db_connection()
    cur = conn.cursor()

    keyword = request.args.get('keyword', '').strip()
    date_filter = request.args.get('date', '').strip()

    purchase_query = '''
        SELECT p.id, p.purchase_date, i.name AS item_name, p.quantity, p.unit_price, p.supplier
        FROM purchases p
        JOIN items i ON p.item_id = i.id
        WHERE i.name LIKE %s AND p.purchase_date LIKE %s
        ORDER BY p.purchase_date DESC
    '''
    usage_query = '''
        SELECT u.id, u.usage_date, i.name AS item_name, u.quantity, u.usage_note
        FROM usages u
        JOIN items i ON u.item_id = i.id
        WHERE i.name LIKE %s AND u.usage_date LIKE %s
        ORDER BY u.usage_date DESC
    '''

    like_keyword = f'%{keyword}%'
    like_date = f'%{date_filter}%'

    cur.execute(purchase_query, (like_keyword, like_date))
    purchases = cur.fetchall()

    cur.execute(usage_query, (like_keyword, like_date))
    usages = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('history.html', purchases=purchases, usages=usages,
                           keyword=keyword, date_filter=date_filter)

@app.route('/edit/<int:item_id>', methods=['GET', 'POST'])
@login_required
def edit_item(item_id):
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        name = request.form['name']
        category = request.form['category']
        unit = request.form['unit']
        stock = int(request.form['stock'])
        min_stock = int(request.form['min_stock'])

        cur.execute('''
            UPDATE items
            SET name = %s, category = %s, unit = %s, stock = %s, min_stock = %s
            WHERE id = %s
        ''', (name, category, unit, stock, min_stock, item_id))

        conn.commit()
        cur.close()
        conn.close()
        return redirect('/stock')

    cur.execute('SELECT * FROM items WHERE id = %s', (item_id,))
    item = cur.fetchone()

    cur.close()
    conn.close()
    return render_template('edit_item.html', item=item)

@app.route('/delete/<int:item_id>')
@login_required
def delete_item(item_id):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute('SELECT name FROM items WHERE id = %s', (item_id,))
    item = cur.fetchone()

    if item:
        flash(f'🗑️ 商品「{item[0]}」を削除しました。')  # ← psycopg2は tuple で返るので item["name"] → item[0]
        cur.execute('DELETE FROM items WHERE id = %s', (item_id,))
        conn.commit()

    cur.close()
    conn.close()
    return redirect(url_for('stock'))


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

from psycopg2.extras import RealDictCursor

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)  # ← RealDictCursorにすると['カラム名']で取得可
    current_month = datetime.now().strftime('%Y-%m')

    # 今月の使用量を合計
    usage_query = '''
        SELECT SUM(quantity) as total_usage
        FROM usages
        WHERE usage_date LIKE %s
    '''
    cur.execute(usage_query, (f'{current_month}%',))
    usage_result = cur.fetchone()
    total_usage = usage_result['total_usage'] or 0  # RealDictCursorならカラム名で取得

    # 在庫切れ間近のアイテム
    cur.execute('SELECT * FROM items WHERE stock <= min_stock')
    low_stock_items = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('dashboard.html',
                           total_usage=total_usage,
                           low_stock_items=low_stock_items)

@app.route('/summary')
@login_required
def summary():
    from collections import defaultdict, OrderedDict

    conn = get_db_connection()
    cur = conn.cursor()

    # PostgreSQLでは strftime → TO_CHAR
    cur.execute('''
        SELECT TO_CHAR(purchase_date, 'YYYY-MM') AS month,
               i.name AS item_name,
               SUM(quantity) AS total
        FROM purchases p
        JOIN items i ON p.item_id = i.id
        GROUP BY month, item_name
    ''')
    purchase_summary = cur.fetchall()

    cur.execute('''
        SELECT TO_CHAR(usage_date, 'YYYY-MM') AS month,
               i.name AS item_name,
               SUM(quantity) AS total
        FROM usages u
        JOIN items i ON u.item_id = i.id
        GROUP BY month, item_name
    ''')
    usage_summary = cur.fetchall()

    cur.close()
    conn.close()

    # データ整形
    temp = defaultdict(lambda: defaultdict(lambda: {'purchase_qty': 0, 'usage_qty': 0}))
    for row in purchase_summary:
        temp[row[0]][row[1]]['purchase_qty'] = row[2]
    for row in usage_summary:
        temp[row[0]][row[1]]['usage_qty'] = row[2]

    summary = OrderedDict()
    for month in sorted(temp.keys(), reverse=True):
        summary[month] = []
        for item_name, qty in temp[month].items():
            summary[month].append({
                'name': item_name,
                'purchase_qty': qty['purchase_qty'],
                'usage_qty': qty['usage_qty']
            })

    return render_template('summary.html', summary=summary)

@app.route('/login', methods=['GET', 'POST'])
def login():
    conn = get_db_connection()
    cur = conn.cursor()
    error = None

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cur.execute('SELECT * FROM users WHERE username = %s', (username,))
        user = cur.fetchone()

        if user and check_password_hash(user[2], password):  # user[2] は password（列の順に注意）
            session['user_id'] = user[0]  # user[0] は id
            flash('✅ ログインしました')
            cur.close()
            conn.close()
            return redirect(url_for('dashboard'))
        else:
            error = 'ログイン失敗：ユーザー名またはパスワードが違います'

    cur.close()
    conn.close()
    return render_template('login.html', error=error)

if __name__ == '__main__':
    app.run()


