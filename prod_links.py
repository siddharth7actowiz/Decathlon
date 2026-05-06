
import requests
import json
import os
from db import *
from urllib.parse import urljoin
import gzip

backup_folder=r"D:\test\decathlon\backup"


headers = {
    "user-agent": "Mozilla/5.0"
}

cookies = {
    'AUTH_STATE': 'eyJhcHAiOiJXTkYifQ%3D%3D',
    'ecom_user_id': '978a1b7e-6473-47fd-b00a-8edeb3cd555b',
    '__cf_bm': 'OGFgc9HZKlkllIEAxaYcXRTh0mIaQt3DscMvjI48pw4-1777882885.5215883-1.0.1.1-oU_1cKdsYEwlhbMK9rM4a41Crjj9sgpJNdtIFjaa16BsADDXrMju5D6ICJaRMyfnLWwIQNxOu6q4TO4mEGSXpXNUsGAapIjNlzZpjqdOm3AjJAYdFlRCqfcuNe7KKtmx',
    '_cfuvid': '68pXh4oX2lxwBCd1EgDltAZrRQ2gpQLYa2hSZRx6jIE-1777882885.5215883-1.0.1.1-iUSAok2srflILj_L_pGWsOlOTfNliGp0kcmj1Y3mqpc',
    'didomi_token': 'eyJ1c2VyX2lkIjoiMTlkZjIxM2YtY2VmOC02M2E3LWI3ODktODU4YzBiZDEyNDhjIiwiY3JlYXRlZCI6IjIwMjYtMDUtMDRUMDg6MjE6MjkuNDU1WiIsInVwZGF0ZWQiOiIyMDI2LTA1LTA0VDA4OjIyOjExLjMzM1oiLCJ2ZXJzaW9uIjoyLCJwdXJwb3NlcyI6eyJlbmFibGVkIjpbIm1hcmtldGluZy1NUlpWcHJlYSIsInBlcnNvbmFsaXMtdGY4cFpUVkgiLCJhbmFseXRpY3MtR01nQldHVGgiXX0sInZlbmRvcnMiOnsiZW5hYmxlZCI6WyJnb29nbGUiLCJjOmFkeWVuLVBqYlljR0N6IiwiYzpnb29nbGVwYXktaXRRcVg4a3EiLCJjOnBheXBhbGZyLThHVW1heTRVIiwiYzphcHBsZXBheS15Y0hIQk10UiIsImM6a2xhcm5hLUJrakZoYTRNIiwiYzp2YWxpdXotWEZoeUZhdFUiLCJjOmZhY2Vib29rYS1ReU1ETEdKUSIsImM6YW1wbGl0dWRlLXE2WmZKVExhIiwiYzpiYW1idXNlci1NeE5icFlCVyIsImM6eXNhbmNlLTN4d0Z4OWU3IiwiYzpyYWt1dGVuYWQtd1FkY3JxTm0iLCJjOnZlcml6b25zdC1hY1RCTDlXYiIsImM6cGludGVyZXN0LVZKR0Y5MkZhIiwiYzp0aWt0b2stRTNaMjZwWTgiLCJjOmlkZWFsby1GR0Q2eGVoRSIsImM6cnRiaG91c2UtQmZ0MnA0ZzIiLCJjOmdvb2dsZXJlbS1SWEhoaVhyUiIsImM6dGVhZHMtY1BNVWkyUWUiLCJjOmRlY2F0aGxvbi04TE45aUNjQyIsImM6Z29vZ2xlYWRzLUFrMzJUUERBIiwiYzpiaW5nLW5MaVFMQUNpIiwiYzptb2JzdWNjZXNzLUdEa2VQTGJYIiwiYzpvZ3VyeS1oa0FpekdmbiIsImM6a2Vsa29vLUZaWWNMemgyIiwiYzpiYXRjaHdlYi0yQTd0SHBhQiIsImM6YXRpbnRlcm5lLUNrOXBXaFlFIiwiYzpkeW5hbWljeWktRVRlYXhIY2siLCJjOmNvbnRlbnRzcS1WeFFjTXpwSCIsImM6c3RhdHNpZy1xYmVDMjdCOCIsImM6YWxnb2xpYS1rZDM0eUN4QSIsImM6Y2xvdWZsYXJlLUhOUldyWVp5IiwiYzptZWRhbGxpYS13bUQ4WmY5aCIsImM6ZGVjYXRobG9uLTJWeWI0eXJuIiwiYzpkYXRhZG9nLXdjclY2SEZYIiwiYzpjYWFzdC1ZeWlXUE1xYyJdfSwidmVuZG9yc19saSI6eyJlbmFibGVkIjpbImdvb2dsZSJdfX0=',
    'euconsent-v2': 'CQjrs8AQjrs8AAHABBENCdFgAP_gAELAAAqIIyQBgAMAAfABUAIQBeYEZALzgBgAqAEIAvMAAAAA.IIyQBgAMAAfABUAIQBeYEZAA.f_wACFgAAAAA',
    '_gcl2_au': '1.1.1951575315.1777882931',
    'dkt_ecom_tracking': 'eyJhbXBsaXR1ZGUiOnsiZGV2aWNlSWQiOiI1ODJjNzc0MC0xNDRhLTQ3NmYtOTE0MS02MmZmZTYyNjQ5ZTkiLCJzZXNzaW9uSWQiOjE3Nzc4ODI5MzEzOTd9fQ==',
    '_gcl_au': '1.1.1767690262.1777882931',
    '__ywtfpcvuid': '38863374601777882931887',
    '__ywtfpcsuid': '13132846301777882931887',
    '_fbp': 'fb.1.1777882932123.883126665276478206',
    '_tt_enable_cookie': '1',
    '_ttp': '01KQS199580RZNW0SRXQ6S11RG_.tt.1',
    '__ywtfpcvuid': '38863374601777882931887',
    '__ywtfpcvuid_refresh': '1778401332478',
    '_cs_c': '0',
    '_pin_unauth': 'dWlkPU5UTmtPVFF4T0RjdFl6Y3dPUzAwTmpjeUxXRXdNREV0TURFeE9EUmhPVEV4WW1abQ',
    'kampyle_userid': '011c-48d4-b827-e274-11a7-6c39-1f11-9620',
    'tfpsi': '793566a0-e029-4548-b287-4328952a3ade',
    'USER_TOKEN_FOR_ANALYTICS': '50a85cc5-68cd-4684-a4aa-7106cd8c591b',
    '_dyjsession': 'fhlkc67yduhery7pnj3itcd89ynxj7se',
    '_dyid_server': '-653020995003066534',
    '__rtbh.uid': '%7B%22eventType%22%3A%22uid%22%2C%22id%22%3A%22unknown%22%2C%22expiryDate%22%3A%222027-05-04T08%3A22%3A52.890Z%22%7D',
    '__rtbh.lid': '%7B%22eventType%22%3A%22lid%22%2C%22id%22%3A%22o82NyXAueaS0j9ciYJpE%22%2C%22expiryDate%22%3A%222027-05-04T08%3A22%3A52.890Z%22%7D',
    'kampyleUserSession': '1777882973295',
    'kampyleUserSessionsCount': '2',
    'kampyleUserPercentile': '25.53473485737371',
    'kampyleSessionPageCounter': '1',
    '_cs_cvars': '%7B%7D',
    '_cs_id': '5ada05f1-e502-a285-fe34-4644759f4aaf.1777882932.1.1777882973.1777882932.1745928109.1812046932638.1.x',
    '_uetsid': '59fd84a0479211f1b44a01b264e34a58|e09v9j|2|g5r|0|2315',
    'ttcsid_CA3M1QBC77U4DS3VBL90': '1777882932409::blqXx8dIX9xzQ6h1kcFC.1.1777882973825.1',
    '_uetvid': '59fdc2d0479211f185bf9d0138f40a8c|rrwz6v|1777882974174|6|1|bat.bing.com/p/insights/c/l',
    '_cs_s': '2.5.U.9.1777884803392',
    '_cs_s_ctx': '%7B%22firstViewTime%22%3A1777882932641%2C%22firstViewUrl%22%3A%22https%3A%2F%2Fwww.decathlon.fr%2Fsearch%3FNtt%3DTimberland%22%2C%22sessionReferrer%22%3A%22https%3A%2F%2Fwww.decathlon.fr%2F%22%7D',
    'mobsuccess.com_tag_js_v2_decathlon_0': '{"clickid":null,"actionsOk":{"duration":[true,true],"nbpages":[]},"duration":90005,"nbpages":2}',
    'ttcsid': '1777882932410::HFSHzNgL3QXS-QlJ5Jv2.1.1777882973825.0::1.37423.41132::98321.6.592.92::96776.110.0',
    '_dd_s': 'aid=45408552-df8b-4f06-8efa-9a35d040417f&rum=2&id=7df0a311-ed03-414e-b241-6f1c05d1661b&created=1777882931669&expire=1777883931987',
}


db = DB()
batch = []
BATCH_SIZE = 100

for color, url in db.fetch_pending_urls("col_urls"):

    print(f"Processing color: {color}")

    # 📁 Create folder per color
    color_folder = os.path.join(backup_folder, color, "pages")
    os.makedirs(color_folder, exist_ok=True)

    params = {
        'pageType': 'search',
        'url': url,
    }

    page_num = 1
    api="https://www.decathlon.fr/api/listing/fr-FR"
    while True:
        response = requests.get(api, params=params, headers=headers, cookies=cookies)
        data = response.json()

        products = data.get("products", [])

        # ✅ SAVE PAGE JSON
        filename = f"page_{page_num}.json.gz"
        filepath = os.path.join(color_folder, filename)

        with gzip.open(filepath, "wt") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"Saved {color} -> {filename} | items: {len(products)}")
        base_url="https://www.decathlon.fr"
        # ✅ EXTRACT PRODUCTS
        for p in products:
            product_id = p.get("supermodelId")
            url=urljoin(base_url,p.get("url"))
            model=p.get("models",[])[0]
            brand=model.get("brand")
            sku_id=model.get("skuId")
            model_id=model.get("id")
           
            batch.append((
                product_id,
                model_id,
                sku_id,
                p.get("label"),
                brand,
                url,
                color,
                "pending"
            ))

        # ✅ INSERT IN BATCH
        if len(batch) >= BATCH_SIZE:
            db.insert_products_batch(batch)
            print(f"Inserted batch of {len(batch)}")
            batch.clear()

        # pagination
        next_page = data.get("pagination", {}).get("next")

        if not next_page:
            break

        params["url"] = "/" + next_page
        page_num += 1

    print(f"Done color: {color}")

# ✅ Insert remaining
if batch:
    db.insert_products_batch(batch)
    print(f"Inserted final batch of {len(batch)}")

db.close()

print("✅ All done!")