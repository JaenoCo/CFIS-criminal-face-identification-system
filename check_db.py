import sqlite3

conn = sqlite3.connect('criminal.db')
cur = conn.cursor()

# Check tables
cur.execute('SELECT name FROM sqlite_master WHERE type="table"')
print('Tables:', cur.fetchall())

# Check record count
cur.execute('SELECT COUNT(*) FROM people')
print('Records count:', cur.fetchone()[0])

# Show sample records
cur.execute('SELECT Id, name, crime, nationality FROM people LIMIT 10')
print('\nSample records:')
for row in cur.fetchall():
    print(f"ID: {row[0]}, Name: {row[1]}, Crime: {row[2]}, Nationality: {row[3]}")

conn.close()
