from flask import Flask, render_template, request, redirect, session, url_for, flash
from datetime import datetime
import psycopg2
from werkzeug.security import check_password_hash

app = Flask(__name__)
app.secret_key = 'my-super-secret-123'

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

        # データベースに追加処理
        conn = get_db_connection()
        conn.execute('INSERT INTO items (name, unit, stock) VALUES (?, ?, ?)', (name, unit, stock))
        conn.commit()
        conn.close()

        flash(f'✅ 商品「{name}」を追加しました。')
        return redirect(url_for('stock'))  # 遷移先でメッセージ表示される
    return render_template('add_item.html')

@app.route('/add_usage', methods=['GET', 'POST'])
@login_required
def add_usage():
    conn = get_db_connection()

    if request.method == 'POST':
        item_id = request.form['item_id']
        usage_date = request.form['usage_date']
        quantity = int(request.form['quantity'])
        usage_note = request.form['usage_note']

        # 現在の在庫数を取得
        current_stock = conn.execute(
            'SELECT stock FROM items WHERE id = ?', (item_id,)
        ).fetchone()['stock']

        # 在庫不足の場合は警告を出して入力ページへ戻す
        if quantity > current_stock:
            items = conn.execute('SELECT * FROM items').fetchall()
            conn.close()
            flash(f'⚠️ 在庫不足です（現在の在庫: {current_stock}）', 'error')
            return render_template('add_usage.html', items=items)

        # 使用情報を追加
        conn.execute('''
            INSERT INTO usages (item_id, usage_date, quantity, usage_note)
            VALUES (?, ?, ?, ?)
        ''', (item_id, usage_date, quantity, usage_note))

        # 在庫を減らす
        conn.execute('''
            UPDATE items SET stock = stock - ?
            WHERE id = ?
        ''', (quantity, item_id))

        conn.commit()
        conn.close()

        flash('✅ 使用情報を追加しました。')
        return redirect(url_for('stock'))

    # GET時：商品一覧を表示
    items = conn.execute('SELECT * FROM items').fetchall()
    conn.close()
    return render_template('add_usage.html', items=items)



@app.route('/add_purchase', methods=['GET', 'POST'])
@login_required
def add_purchase():
    conn = get_db_connection()

    if request.method == 'POST':
        item_id = request.form['item_id']
        purchase_date = request.form['purchase_date']
        quantity = int(request.form['quantity'])
        unit_price = float(request.form['unit_price']) if request.form['unit_price'] else None
        supplier = request.form['supplier']

        # purchases に追加
        conn.execute('''
            INSERT INTO purchases (item_id, purchase_date, quantity, unit_price, supplier)
            VALUES (?, ?, ?, ?, ?)
        ''', (item_id, purchase_date, quantity, unit_price, supplier))

        # 在庫を更新
        conn.execute('''
            UPDATE items SET stock = stock + ?
            WHERE id = ?
        ''', (quantity, item_id))

        conn.commit()
        conn.close()

        # フィードバック
        flash('✅ 仕入れを追加しました。')
        return redirect(url_for('stock'))

    # GETメソッドの場合
    items = conn.execute('SELECT * FROM items').fetchall()
    conn.close()
    return render_template('add_purchase.html', items=items)


@app.route('/stock')
@login_required
def stock():
    conn = get_db_connection()
    items = conn.execute('SELECT * FROM items').fetchall()
    conn.close()
    return render_template('stock.html', items=items)


@app.route('/history', methods=['GET', 'POST'])
@login_required
def history():
    conn = get_db_connection()

    keyword = request.args.get('keyword', '').strip()
    date_filter = request.args.get('date', '').strip()

    purchase_query = '''
        SELECT p.id, p.purchase_date, i.name AS item_name, p.quantity, p.unit_price, p.supplier
        FROM purchases p
        JOIN items i ON p.item_id = i.id
        WHERE i.name LIKE ? AND p.purchase_date LIKE ?
        ORDER BY p.purchase_date DESC
    '''
    usage_query = '''
        SELECT u.id, u.usage_date, i.name AS item_name, u.quantity, u.usage_note
        FROM usages u
        JOIN items i ON u.item_id = i.id
        WHERE i.name LIKE ? AND u.usage_date LIKE ?
        ORDER BY u.usage_date DESC
    '''

    like_keyword = f'%{keyword}%'
    like_date = f'%{date_filter}%'

    purchases = conn.execute(purchase_query, (like_keyword, like_date)).fetchall()
    usages = conn.execute(usage_query, (like_keyword, like_date)).fetchall()

    conn.close()
    return render_template('history.html', purchases=purchases, usages=usages,
                           keyword=keyword, date_filter=date_filter)
@app.route('/edit/<int:item_id>', methods=['GET', 'POST'])
@login_required
def edit_item(item_id):
    conn = get_db_connection()

    if request.method == 'POST':
        name = request.form['name']
        category = request.form['category']
        unit = request.form['unit']
        stock = int(request.form['stock'])
        min_stock = int(request.form['min_stock'])

        conn.execute('''
            UPDATE items
            SET name = ?, category = ?, unit = ?, stock = ?, min_stock = ?
            WHERE id = ?
        ''', (name, category, unit, stock, min_stock, item_id))

        conn.commit()
        conn.close()
        return redirect('/stock')

    item = conn.execute('SELECT * FROM items WHERE id = ?', (item_id,)).fetchone()
    conn.close()
    return render_template('edit_item.html', item=item)

@app.route('/delete/<int:item_id>')
def delete_item(item_id):
    conn = get_db_connection()
    cur = conn.execute('SELECT name FROM items WHERE id = ?', (item_id,))
    item = cur.fetchone()
    if item:
        flash(f'🗑️ 商品「{item["name"]}」を削除しました。')
        conn.execute('DELETE FROM items WHERE id = ?', (item_id,))
        conn.commit()
    conn.close()
    return redirect(url_for('stock'))

    from collections import defaultdict, OrderedDict

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    conn = get_db_connection()
    current_month = datetime.now().strftime('%Y-%m')

    # 今月の使用量を合計
    usage_query = '''
        SELECT SUM(quantity) as total_usage
        FROM usages
        WHERE usage_date LIKE ?
    '''
    usage_result = conn.execute(usage_query, (f'{current_month}%',)).fetchone()
    total_usage = usage_result['total_usage'] or 0

    # 在庫切れ間近（min_stock以下）の商品
    low_stock_items = conn.execute('SELECT * FROM items WHERE stock <= min_stock').fetchall()

    conn.close()

    return render_template('dashboard.html',
                           total_usage=total_usage,
                           low_stock_items=low_stock_items)

@app.route('/summary')
@login_required
def summary():
    from collections import defaultdict, OrderedDict

    conn = get_db_connection()

    purchase_summary = conn.execute('''
        SELECT strftime('%Y-%m', purchase_date) AS month,
               i.name AS item_name,
               SUM(quantity) AS total
        FROM purchases p
        JOIN items i ON p.item_id = i.id
        GROUP BY month, item_name
    ''').fetchall()

    usage_summary = conn.execute('''
        SELECT strftime('%Y-%m', usage_date) AS month,
               i.name AS item_name,
               SUM(quantity) AS total
        FROM usages u
        JOIN items i ON u.item_id = i.id
        GROUP BY month, item_name
    ''').fetchall()

    conn.close()

    temp = defaultdict(lambda: defaultdict(lambda: {'purchase_qty': 0, 'usage_qty': 0}))
    for row in purchase_summary:
        temp[row['month']][row['item_name']]['purchase_qty'] = row['total']
    for row in usage_summary:
        temp[row['month']][row['item_name']]['usage_qty'] = row['total']

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
def login():  # ← 関数名を login_page にして重複防止！
    conn = get_db_connection()
    error = None

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            flash('✅ ログインしました')
            return redirect(url_for('dashboard'))
        else:
            error = 'ログイン失敗：ユーザー名またはパスワードが違います'

    conn.close()
    return render_template('login.html', error=error)

if __name__ == '__main__':
    print("Flaskアプリを起動します")
    app.run(debug=True)

