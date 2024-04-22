from fastapi import FastAPI, HTTPException
import sqlite3
from datetime import datetime

app = FastAPI()

def connect_database():
    conn = sqlite3.connect('library.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS books (
                 book_id TEXT PRIMARY KEY,
                 title TEXT,
                 author TEXT,
                 issued INTEGER DEFAULT 0
             )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                 user_id INTEGER PRIMARY KEY,
                 name TEXT 
             )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
                 transaction_id INTEGER PRIMARY KEY,
                 user_id INTEGER,
                 book_id TEXT,
                 date_issued TEXT,
                 date_returned TEXT,
                 FOREIGN KEY (user_id) REFERENCES users(user_id),
                 FOREIGN KEY (book_id) REFERENCES books(book_id)
             )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS payments (
                 user_id INTEGER,
                 fine INTEGER,
                 FOREIGN KEY (user_id) REFERENCES users(user_id)
             )''')
    conn.commit()
    return conn

@app.post("/users/")
async def add_user(user_id: int, name: str):
    conn = connect_database()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (user_id, name) VALUES (?, ?)", (user_id, name))
        conn.commit()
        return {"message": "User added successfully."}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="User ID already exists.")
    
@app.post("/books/")
async def add_book(book_id: str, title: str, author: str):
    conn = connect_database()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO books (book_id, title, author, issued) VALUES (?, ?, ?, 0)", (book_id, title, author))
        conn.commit()
        return {"message": "Book added successfully."}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Book ID already exists")

@app.get("/users/")
async def show_users():
    conn = connect_database()
    c = conn.cursor()
    c.execute("SELECT * FROM users")
    users = c.fetchall()
    if users:
        return {"Users": [{"user_id": user[0], "name": user[1]} for user in users]}
    else:
        return {"message": "No users found"}
    
@app.post("/issue-book/")
async def issue_book(user_id: int, book_id: str):
    conn = connect_database()
    c = conn.cursor()
    book = c.execute("SELECT * FROM books WHERE book_id=? AND issued=0", (book_id,)).fetchone()
    if book:
        c.execute("UPDATE books SET issued=1 WHERE book_id=?", (book_id,))
        current_date = datetime.now().strftime('%Y-%m-%d')
        c.execute("INSERT INTO transactions (user_id, book_id, date_issued) VALUES (?, ?, ?)", (user_id, book_id, current_date))
        conn.commit()
        return {"message": f"Book {book_id} issued to User {user_id} successfully."}
    else:
        raise HTTPException(status_code=400, detail="Book not available.")
    
@app.post("/return-book/")
async def return_book(user_id: int, book_id: str):
    conn = connect_database()
    c = conn.cursor()
    c.execute("SELECT * FROM transactions WHERE user_id=? AND book_id=?", (user_id, book_id))
    transaction_row = c.fetchone()
    if transaction_row:
        c.execute("UPDATE books SET issued=0 WHERE book_id=?", (book_id,))
        current_date = datetime.now().strftime('%Y-%m-%d')
        c.execute("UPDATE transactions SET date_returned=? WHERE transaction_id=?", (current_date, transaction_row[0]))
        conn.commit()

        transaction_date = transaction_row[3]
        fine_amount = calculate_fine(transaction_date, current_date)
        if fine_amount > 0:
            c.execute("INSERT INTO payments (user_id, fine) VALUES (?, ?)", (user_id, fine_amount))
            conn.commit()
        return {"message": "Book returned successfully."}
    else:
        raise HTTPException(status_code=400, detail="Book not borrowed by the user.")
     
@app.get("/user-history/{user_id}")
async def display_user_history(user_id: int):
    conn = connect_database()
    c = conn.cursor()
    c.execute("""
        SELECT
            transactions.book_id,
            books.title,
            transactions.date_issued,
            transactions.date_returned,
            SUM(payments.fine) AS total_fine
        FROM
            transactions
            LEFT JOIN books ON transactions.book_id = books.book_id
            LEFT JOIN payments ON transactions.user_id = payments.user_id
        WHERE
            transactions.user_id=?
        GROUP BY
            transactions.book_id
    """, (user_id,))
    
    history = c.fetchall()
    if history:
        user_history = []
        for item in history:
            fine_description = 'No fine payment, returned on time' if item[3] else f'Rs.{item[4]}'
            user_history.append({
                "Book ID": item[0],
                "Title": item[1],
                "Date Issued": item[2],
                "Date Returned": item[3],
                "Fine Paid": fine_description
            })
        return {"User Borrowing History": user_history}
    else:
        return {"message": "No borrowing history found for the user."}
    
def calculate_fine(transaction_date, return_date):
    transaction_date = datetime.strptime(transaction_date, '%Y-%m-%d')
    return_date = datetime.strptime(return_date, '%Y-%m-%d')
    days_overdue = (return_date - transaction_date).days
    if days_overdue > 0:
        return days_overdue * 10
    else:
        return 0
