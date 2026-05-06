import pandas as pd
import json
from sqlalchemy import create_engine

# Create DB connection
engine = create_engine("mysql+pymysql://root:actowiz@localhost/decathlone")

# Query data
query = "SELECT * FROM decathlon_pdp "
df = pd.read_sql(query, engine)
# df =  df.head(1000)

print("Shape:", df.shape)

# 1. Replace NULL
df = df.fillna("N/A")

# 2. Replace empty strings
df.replace(r'^\s*$', "N/A", regex=True, inplace=True)

# 3. Replace [] and {}
df.replace(["[]","null", "{}"], "N/A", inplace=True)

# 4. Replace 0 → N/A (only text columns)
for col in df.select_dtypes(include=["object", "string"]).columns:
    df[col] = df[col].replace(0, "N/A")



# cols_to_fix = ["average_rating", "total_ratings","price_difference","discount_percentage"]
# for col in cols_to_fix:
#     if col in df.columns:
#         df[col] = df[col].replace(0, "N/A")


if 'product_name' in df.columns:
    # Get the column index of productname
    col_index = df.columns.get_loc('product_name')

    # Create a list of columns in order
    cols = df.columns.tolist()

    # Insert 'brand' right after 'productname'
    cols.insert(col_index + 1, 'brand')

    # Add the brand column with TIMBERLAND value
    df['brand'] = 'TIMBERLAND'

    # Reorder columns
    df = df[cols]


def update_fabricant(specs):
    # Check if specifications is a dictionary and has the 'fabricant' key
    if isinstance(specs, dict) and 'fabricant' in specs:
        # Add the 'about' key with the text from your image
        specs['fabricant']['about'] = (
            "Ce contact assure le suivi de la sécurité et de la conformité des produits. "
            "Si votre demande concerne une commande ou un retour, contactez notre service client."
        )
    return specs


# Apply the function to the specifications column
if 'specifications' in df.columns:
    # Ensure the column is parsed as a dict if it's currently a string
    df['specifications'] = df['specifications'].apply(
        lambda x: json.loads(x) if isinstance(x, str) and x != "N/A" else x)

    # Update the dictionary
    df['specifications'] = df['specifications'].apply(update_fabricant)
# Save to Excel
df.to_excel("decathlon.xlsx", index=False)

print("✅ Done (FINAL CLEAN VERSION)")