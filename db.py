import mysql.connector
import json
class DB:
    def __init__(self):
        self.host = "localhost"
        self.user = "root"
        self.password = "actowiz"
        self.database = "decathlone"

        #  Step 1: connect WITHOUT database
        self.conn = mysql.connector.connect(
            host=self.host,
            user=self.user,
            password=self.password
        )
        self.cursor = self.conn.cursor()

        #  Step 2: create DB if not exists
        self.cursor.execute(f"CREATE DATABASE IF NOT EXISTS {self.database}")

        #  Step 3: connect to DB
        self.conn.database = self.database

        #  Step 4: create tables
        self.create_tables()

    # ✅ Create tables
    def create_tables(self):

        # products table
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS products_links (
            id INT AUTO_INCREMENT PRIMARY KEY,
            product_id VARCHAR(100),
        model_id VARCHAR(100),
        sku_id VARCHAR(100) UNIQUE,
        product_name TEXT,
        brand VARCHAR(100),
        product_url TEXT,
        color VARCHAR(50),
        status VARCHAR(20) DEFAULT 'pending'
        )
        """)

        # col_urls table (if not already created)
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS col_urls (
            id INT AUTO_INCREMENT PRIMARY KEY,
            color VARCHAR(50),
            url TEXT,
            status VARCHAR(20) DEFAULT 'pending'
        )
        """)

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS decathlon_pdp (
            id INT AUTO_INCREMENT PRIMARY KEY,
            category_hierarchy JSON,
            sku_id VARCHAR(100) ,
            product_id VARCHAR(100),

            product_name TEXT,
            color VARCHAR(50),

            mrp DECIMAL(10,2),
            selling_price DECIMAL(10,2),
            discount_percentage INT,

            images JSON,
            sizes JSON,
            short_description TEXT,
            description TEXT,

            specifications JSON,
            return_policy JSON,

            seller_name VARCHAR(255),
            shipped_by VARCHAR(255),

            reviews_count INT,
            average_review FLOAT,
            reviews JSON,
            product_url VARCHAR(500) UNIQUE
        )
        """)

        self.conn.commit()

    # ✅ Fetch URLs
    def fetch_pending_urls(self, table):
        if table == "products_links":
            query = """
            SELECT color, product_url AS url
            FROM products_links
            WHERE status='pending'
            """
        else:
            query = f"SELECT color, url FROM {table} WHERE status='pending'"

        self.cursor.execute(query)
        return self.cursor.fetchall() or []

    # ✅ Batch insert
    def insert_products_batch(self, data):
        query = """
        INSERT INTO products_links (
            product_id,
            model_id,
            sku_id,
            product_name,
            brand,
            product_url,
            color,
            status
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            product_name = VALUES(product_name),
            brand = VALUES(brand),
            product_url = VALUES(product_url),
            color = VALUES(color),
            status = VALUES(status)
        """
        self.cursor.executemany(query, data)
        self.conn.commit()

    def insert_pdp_batch(self, data_list):
        query = """
        INSERT IGNORE INTO decathlon_pdp (
            category_hierarchy,sku_id, product_id, product_name, color,
            mrp, selling_price, discount_percentage,
            images, sizes,short_description, description,
            specifications, return_policy,
            seller_name, shipped_by,
            reviews_count, average_review, reviews,product_url
        )
        VALUES (%s, %s,%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,%s)
        """

        values = []

        for item in data_list:
            values.append((
                json.dumps(item.get("category_hierarchy")),
                item.get("sku_id"),
                item.get("product_id"),
                item.get("product_name"),
                item.get("color"),

                item.get("mrp"),
                item.get("selling_price"),
                item.get("discount_percentage"),

                json.dumps(item.get("images")),  # ✅ here
                json.dumps(item.get("size")),  # ✅ here
                item.get("short_description"),
                item.get("description"),

                json.dumps(item.get("specifications")),  # ✅ here
                json.dumps(item.get("return_policy")),  # ✅ here

                item.get("seller_name"),
                item.get("shipped_by"),

                item.get("reviews_count"),
                item.get("average_review"),
                json.dumps(item.get("reviews")) ,
                item.get("product_url")# ✅ here
            ))

        self.cursor.executemany(query, values)
        self.conn.commit()
    # ✅ Update status
    def mark_done(self, table, url):
        if table == "products_links":
            query = f"UPDATE {table} SET status='done' WHERE product_url=%s"
            self.cursor.execute(query, (url,))
            self.conn.commit()
        else:
            query = f"UPDATE {table} SET status='done' WHERE url=%s"
            self.cursor.execute(query, (url,))
            self.conn.commit()

    def close(self):
        self.cursor.close()
        self.conn.close()