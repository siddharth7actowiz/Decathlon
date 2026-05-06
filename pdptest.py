from textwrap import indent

import requests
from curl_cffi import requests as curl_requests
from lxml import html
import json
import re
from parsel import Selector
import os
import gzip
from db import DB
import sys

#BACK_UP
pdp_backup=r"D:\test\decathlon\pdp_backup\pdp"
reviews_backup=r"D:\test\decathlon\pdp_backup\reviews"

#helper functions
def clean_json_data(raw_script):
    """
    Clean and extract JSON from the raw script
    """
    if not raw_script:
        return None
    
    # Extract after colon (handles any number)
    match = re.search(r'[0-9a-f]+:(.+)$', raw_script, re.DOTALL)
    if not match:
        return None
    
    json_str = match.group(1)
    
    # Clean the string
    json_str = json_str.replace('\\"', '"')
    json_str = json_str.replace('\\\\', '\\')
    json_str = json_str.replace('\\n', ' ')
    json_str = json_str.replace('\\t', ' ')
    json_str = json_str.replace('\\r', ' ')
    json_str = json_str.replace('\\u003c', '<')
    json_str = json_str.replace('\\u003e', '>')
    json_str = json_str.replace('$undefined', 'null')
    json_str = re.sub(r'\$L\d+[a-f]?', 'null', json_str)
    json_str = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', json_str)
    
    # Remove trailing characters
    json_str = json_str.replace('"])', '')
    
    # Parse JSON
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"JSON decode error in clean_json_data: {e}")
        return None


def fetch_reviews(modelid, sku_id, headers, cookies):
    params = {
        'nbItemsPerPage': '3',
        'page': '0',
    }

    # Determine which type of product this is
    if isinstance(sku_id, str) and '-' in sku_id:
        # Marketplace product (UUID format)
        endpoint = f'https://www.decathlon.fr/api/reviews/fr-FR/reviews-stats/{sku_id}/onecatalog_product'
    else:
        # Regular Decathlon product (numeric)
        endpoint = f'https://www.decathlon.fr/api/reviews/fr-FR/reviews-stats/{sku_id}/product'

    print(f"Fetching: {endpoint}")
    response = requests.get(endpoint, params=params, cookies=cookies, headers=headers)
    review_data = response.json()

    distribution_counts = {
        "1": 0,
        "2": 0,
        "3": 0,
        "4": 0,
        "5": 0,
    }

    stats = review_data.get("stats", {})
    total_reviews = stats.get("count", 0)

    if total_reviews > 0:
        rating_distribution = stats.get("ratingDistribution", [])
        for rating in rating_distribution:
            code = rating.get("code")
            value = rating.get("value")
            if code and code in distribution_counts:
                distribution_counts[code] = value

    # print(f"Total reviews: {total_reviews}")
    # print(f"Distribution: {distribution_counts}")

    return distribution_counts


def clean_decimal(val):
    if val in (None, "null", "", "None"):
        return None
    try:
        return float(val)
    except:
        return None

def process_product(color, url, headers, cookies, worker_id):
    session = curl_requests.Session(impersonate="chrome124")

    try:
        response = session.get(url, cookies=cookies, headers=headers)
        product_url = url

        print(f"[Worker {worker_id}] {url} -> {response.status_code}")

        if not response.ok:
            return None

        tree = html.fromstring(response.text)
        paragraphs = tree.xpath('//div[@class="product-info-item__description-marketplace"]//p/text()')  
        description = ' '.join(paragraphs)  # 
        script = tree.xpath(
            'string(//script[contains(text(), "self.__next_f.push") and contains(text(), "itemGroup")])'
        )

        return_policy_script = tree.xpath(
            'string(//script[contains(text(), "self.__next_f.push") and contains(text(), "translations")])'
        )

        if not script:
            print(f"[Worker {worker_id}] No script found")
            return None

        json_data = clean_json_data(script)
        if not json_data:
            print(f"[Worker {worker_id}] JSON failed")
            return None

        # ---------------- RETURN POLICY ----------------
        return_policy_data = {}

        if return_policy_script:
            return_data = clean_json_data(return_policy_script)

            if isinstance(return_data, list) and len(return_data) > 3:
                block = return_data[3]
                if isinstance(block, dict):
                    translations = block.get("translations") or {}
                    product_assurance = translations.get("ProductAssurance") or {}

                    return_policy_data = {
                        "policy": product_assurance.get("returnWithin30days"),
                        "detail": product_assurance.get("returnDescription3P")
                    }

        # ---------------- ITEM GROUP ----------------
        product_info = {}

        if isinstance(json_data, list):
            if len(json_data) > 3 and isinstance(json_data[3], list):
                if len(json_data[3]) > 3 and isinstance(json_data[3][3], dict):
                    product_info = json_data[3][3].get("itemGroup") or {}

            if not product_info:
                for item in json_data:
                    if isinstance(item, dict) and isinstance(item.get("itemGroup"), dict):
                        product_info = item["itemGroup"]
                        break
                    elif isinstance(item, list) and len(item) > 3:
                        if isinstance(item[3], dict) and isinstance(item[3].get("itemGroup"), dict):
                            product_info = item[3]["itemGroup"]
                            break

        if not isinstance(product_info, dict):
            print(f"[Worker {worker_id}] Invalid product_info")
            return None

        # ---------------- SKU GROUP ----------------
        skugrp = product_info.get("skuGroups") or []
        if not isinstance(skugrp, list) or not skugrp:
            return None

        skugrp0 = skugrp[0] if isinstance(skugrp[0], dict) else {}
        skus_list = skugrp0.get("skus") or []

        if not isinstance(skus_list, list):
            skus_list = []

        model_id = skugrp0.get("modelId")
        sku_id = product_info.get("representativeSku")
        #Pagesave
        file = f"{sku_id}.html.gz"
        filepath=os.path.join(pdp_backup,file)
        with gzip.open(filepath, "wt",encoding="utf-8") as f:
            f.write(response.text)

        # Category Hierarchy
        bread = tree.xpath(
            '//div[@data-cs-override-id="product-header_breadcrumbs"]//script[@type="application/ld+json"]/text()')
        if bread:
            cate_data = json.loads(bread[0])  # Get first script tag content

            categories = []
            # Iterate over itemListElement
            for item in cate_data.get("itemListElement", []):
                name = item.get("name", "")
                # Skip "Home" (position 1)
                if name and name.lower() != "home":
                    categories.append(name)

            # Convert to L1, L2 format
            category_hierarchy = {}
            for i, name in enumerate(categories, 1):
                category_hierarchy[f"l{i}"] = name

        # ---------------- OUTPUT ----------------
        temp_data = {
            "category_hierarchy":category_hierarchy,
            "color": color,
            "product_id": product_info.get("id"),
            "sku_id": sku_id,
            "product_name": None,
            "images": [],
            "size": [],
            "specifications": {},
            "return_policy": return_policy_data,
            "product_url": product_url
        }

        if skus_list and isinstance(skus_list[0], dict):
            temp_data["product_name"] = skus_list[0].get("title")

        # ---------------- PRICE (SAFE) ----------------
        try:
            if skus_list and isinstance(skus_list[0], dict):
                offers = (skus_list[0].get("offers") or [{}])[0] or {}
                fixed_prices = (offers.get("fixedPrices") or [{}])[0] or {}
                type_targets = (fixed_prices.get("typeTargets") or [{}])[0] or {}
                currencies = type_targets.get("currencies") or {}
                main_currency = currencies.get("main") or {}

                mrp = clean_decimal(main_currency.get("referenceValueWithTaxes"))
                selling_price = clean_decimal(main_currency.get("valueWithTaxes"))
                disc_per = main_currency.get("discountPercentage")

                temp_data["mrp"] = mrp if mrp else selling_price
                temp_data["selling_price"] = selling_price
                temp_data["discount_percentage"] = (
                    int(disc_per) if isinstance(disc_per, (int, float, str)) and str(disc_per).replace('.', '', 1).isdigit()
                    else None
                )
        except:
            pass

        # ---------------- IMAGES ----------------
        if skus_list and isinstance(skus_list[0], dict):
            images = skus_list[0].get("images") or []
            temp_data["images"] = [
                i.get("url") for i in images
                if isinstance(i, dict) and i.get("url")
            ]

        # ---------------- COLORS ----------------
        if skus_list and isinstance(skus_list[0], dict):
            colors = skus_list[0].get("colors") or []

            temp_data["color"] = colors[0] if colors else None

        # ---------------- SIZES ----------------
        for size in skus_list:
            if not isinstance(size, dict):
                continue

            try:
                offers = (size.get("offers") or [{}])[0] or {}
                fixed_prices = (offers.get("fixedPrices") or [{}])[0] or {}
                type_targets = (fixed_prices.get("typeTargets") or [{}])[0] or {}
                currencies = type_targets.get("currencies") or {}
                main_currency = currencies.get("main") or {}

                temp_data["size"].append({
                    "size": size.get("sizeLabel"),
                    "price": main_currency.get("valueWithTaxes")
                })
            except:
                continue

        # ---------------- REVIEWS ----------------
        reviews = product_info.get("reviews")

        if isinstance(reviews, dict):
            average = reviews.get("average")

            try:
                avg_rating = round(float(average), 1) if average not in (None, "null", "") else None
            except:
                avg_rating = None

            temp_data["reviews_count"] = reviews.get("count")
            temp_data["average_review"] = avg_rating
            temp_data["reviews"] = fetch_reviews(model_id, sku_id, headers, cookies)

        # ---------------- SELLER ----------------
        sku_conditions = skugrp0.get("skuGroupConditions") or []
        if isinstance(sku_conditions, list) and sku_conditions:
            cond0 = sku_conditions[0] if isinstance(sku_conditions[0], dict) else {}

            seller = cond0.get("seller") or {}
            fulfiller = cond0.get("fulfiller") or {}

            temp_data["seller_name"] = seller.get("name")
            temp_data["shipped_by"] = fulfiller.get("name")

        # ---------------- DESCRIPTION ----------------
        #short_desc
        skus_list = skugrp[0].get("skus", [])
        if skus_list:
            temp_data["short_description"] = skus_list[0].get("catchline")
        desc = skus_list[0].get("description") if skus_list and isinstance(skus_list[0], dict) else ""
        if description:
            temp_data["description"] =description
        else:
            selector = Selector(text=desc)
            temp_data["description"] = ''.join(selector.xpath('//text()').getall()).strip()


        # ---------------- SPECIFICATIONS ----------------
        details = {}

        if skus_list and isinstance(skus_list[0], dict):
            for char in skus_list[0].get("characteristics") or []:
                if not isinstance(char, dict):
                    continue

                values = char.get("values") or []
                if values and isinstance(values[0], dict):
                    key = char.get("name")
                    value = values[0].get("name")

                    if key and value not in (None, "", "null"):
                        details[key] = value

        fabricant = {}
        if skus_list and isinstance(skus_list[0], dict):
            raw_fabricant = skus_list[0].get("manufacturer")
            if isinstance(raw_fabricant, dict):
                fabricant = raw_fabricant

        fabricant_data = {
            "name": fabricant.get("name"),
            "address": fabricant.get("postalAddress"),
            "email": fabricant.get("contactAddress")
        }

        # remove empty values
        fabricant_data = {
            k: v for k, v in fabricant_data.items()
            if v not in (None, "", "null")
        }

        # ---------------- FINAL DECISION ----------------
        if details or fabricant_data:
            temp_data["specifications"] = {}

            if details:
                temp_data["specifications"]["details"] = details

            if fabricant_data:
                temp_data["specifications"]["fabricant"] = fabricant_data
        else:
            temp_data["specifications"] = None
        print(temp_data)
        print(f"[Worker {worker_id}] Done: {sku_id}")

        return temp_data

    except Exception as e:
        print(f"[Worker {worker_id}] Fatal error: {e}")
        return None



def parse(worker_id=0, total_workers=1):
    cookies = {
        'AUTH_STATE': 'eyJhcHAiOiJXTkYifQ%3D%3D',
        'ecom_user_id': '978a1b7e-6473-47fd-b00a-8edeb3cd555b',
        'didomi_token': 'eyJ1c2VyX2lkIjoiMTlkZjIxM2YtY2VmOC02M2E3LWI3ODktODU4YzBiZDEyNDhjIiwiY3JlYXRlZCI6IjIwMjYtMDUtMDRUMDg6MjE6MjkuNDU1WiIsInVwZGF0ZWQiOiIyMDI2LTA1LTA0VDA4OjIyOjExLjMzM1oiLCJ2ZXJzaW9uIjoyLCJwdXJwb3NlcyI6eyJlbmFibGVkIjpbIm1hcmtldGluZy1NUlpWcHJlYSIsInBlcnNvbmFsaXMtdGY4cFpUVkgiLCJhbmFseXRpY3MtR01nQldHVGgiXX0sInZlbmRvcnMiOnsiZW5hYmxlZCI6WyJnb29nbGUiLCJjOmFkeWVuLVBqYlljR0N6IiwiYzpnb29nbGVwYXktaXRRcVg4a3EiLCJjOnBheXBhbGZyLThHVW1heTRVIiwiYzphcHBsZXBheS15Y0hIQk10UiIsImM6a2xhcm5hLUJrakZoYTRNIiwiYzp2YWxpdXotWEZoeUZhdFUiLCJjOmZhY2Vib29rYS1ReU1ETEdKUSIsImM6YW1wbGl0dWRlLXE2WmZKVExhIiwiYzpiYW1idXNlci1NeE5icFlCVyIsImM6eXNhbmNlLTN4d0Z4OWU3IiwiYzpyYWt1dGVuYWQtd1FkY3JxTm0iLCJjOnZlcml6b25zdC1hY1RCTDlXYiIsImM6cGludGVyZXN0LVZKR0Y5MkZhIiwiYzp0aWt0b2stRTNaMjZwWTgiLCJjOmlkZWFsby1GR0Q2eGVoRSIsImM6cnRiaG91c2UtQmZ0MnA0ZzIiLCJjOmdvb2dsZXJlbS1SWEhoaVhyUiIsImM6dGVhZHMtY1BNVWkyUWUiLCJjOmRlY2F0aGxvbi04TE45aUNjQyIsImM6Z29vZ2xlYWRzLUFrMzJUUERBIiwiYzpiaW5nLW5MaVFMQUNpIiwiYzptb2JzdWNjZXNzLUdEa2VQTGJYIiwiYzpvZ3VyeS1oa0FpekdmbiIsImM6a2Vsa29vLUZaWWNMemgyIiwiYzpiYXRjaHdlYi0yQTd0SHBhQiIsImM6YXRpbnRlcm5lLUNrOXBXaFlFIiwiYzpkeW5hbWljeWktRVRlYXhIY2siLCJjOmNvbnRlbnRzcS1WeFFjTXpwSCIsImM6c3RhdHNpZy1xYmVDMjdCOCIsImM6YWxnb2xpYS1rZDM0eUN4QSIsImM6Y2xvdWZsYXJlLUhOUldyWVp5IiwiYzptZWRhbGxpYS13bUQ4WmY5aCIsImM6ZGVjYXRobG9uLTJWeWI0eXJuIiwiYzpkYXRhZG9nLXdjclY2SEZYIiwiYzpjYWFzdC1ZeWlXUE1xYyJdfSwidmVuZG9yc19saSI6eyJlbmFibGVkIjpbImdvb2dsZSJdfX0=',
        'euconsent-v2': 'CQjrs8AQjrs8AAHABBENCdFgAP_gAELAAAqIIyQBgAMAAfABUAIQBeYEZALzgBgAqAEIAvMAAAAA.IIyQBgAMAAfABUAIQBeYEZAA.f_wACFgAAAAA',
        '_gcl2_au': '1.1.1951575315.1777882931',
        '__ywtfpcvuid': '38863374601777882931887',
        '_fbp': 'fb.1.1777882932123.883126665276478206',
        '_tt_enable_cookie': '1',
        '_ttp': '01KQS199580RZNW0SRXQ6S11RG_.tt.1',
        '__ywtfpcvuid': '38863374601777882931887',
        '__ywtfpcvuid_refresh': '1778401332478',
        '_cs_c': '0',
        '_pin_unauth': 'dWlkPU5UTmtPVFF4T0RjdFl6Y3dPUzAwTmpjeUxXRXdNREV0TURFeE9EUmhPVEV4WW1abQ',
        'kampyle_userid': '011c-48d4-b827-e274-11a7-6c39-1f11-9620',
        'USER_TOKEN_FOR_ANALYTICS': '50a85cc5-68cd-4684-a4aa-7106cd8c591b',
        '_dyid_server': '-653020995003066534',
        '_gcl_au': '1.1.1767690262.1777882931.1460436215.1777981565.1777981567',
        'cf_clearance': 'f.LXDSyRtx8voqbczPOW5rxEKV8JWA840zK7XrZ9_lU-1777981984-1.2.1.1-YfYqQrZyuM9A6n9Hpoi51isaEFKXBZ2feJQd4dQ2UpNaf7Evax7EkPO0WywNKKhpiRbqMe5_aEVKPDE5BlCBlAqaX8DyU57dPTcSnn3lEhrzKGOtXy8l8kAc90BwbJCI5BDFG.UqUBIeIeLrVTujocdoiZ2Y2eJO5YvAyovLxfEssHRuLn8Y8UCmIium6qyGJLv0ubiukreg3nX3hSELBBW3m_rmHF_zk7z07YvbS7coc_gyF5Tuc1bc88WJ.AKkCPs0qWHUWAYNBzSYaE6v7xZhwliCTm1Ki6pacF_6v9JswzzTjL6VhEJ2I.qJREWhztJpGwc58w1xqq7kpFbwvg',
        '_dyjsession': 'z51e4zcit8cpq2wb0p3ap4pazrlydd0a',
        'dkt_ecom_tracking': 'eyJhbXBsaXR1ZGUiOnsiZGV2aWNlSWQiOiI1ODJjNzc0MC0xNDRhLTQ3NmYtOTE0MS02MmZmZTYyNjQ5ZTkiLCJzZXNzaW9uSWQiOjE3NzgwNDI4MzY2MzV9fQ==',
        '__ywtfpcsuid': '22227612341778042839767',
        '_cs_cvars': '%7B%7D',
        'tfpsi': '0aa04af1-d16a-4bcb-95ec-7829a18946f9',
        'kampyleUserSession': '1778042859446',
        'kampyleUserSessionsCount': '45',
        'kampyleUserPercentile': '81.15545816216752',
        '__cf_bm': 'sNik2n8nlogKlyoMo0o6thxaoxOYTSk8f3YQM81VuvI-1778042908.6161523-1.0.1.1-0zJ8AySB6DvGUFNRB3OUa1k6HXwwQcgbrT4Ev9Wy.oCDBRmblTQ6B4ulV4cvHCS9hNzUbwxhbno2SG11rJm8BIRv8mXPirfgXMGZfmZTCiCHPGb8IiteAAdhpYDVGDxU',
        '_cfuvid': '8OXh6XwYdNgrwRMJcQOApkfljRUOJV_zCgKdCvwbWpw-1778042908.6161523-1.0.1.1-rau.cNs7WAIEqRV6INnc_5D7dF7zQ5Ndh4cT34D5xgw',
        'CUSTOMER_LVP': '[[%229a542c73-249b-46a5-8368-6b4286d5297b%22%2C%2238c190df-624c-4b6f-b06d-0ed4f9440826%22]%2C[%22338961%22%2C%22028ffdfc-b8fe-4926-aaf9-f5be6c8bda10%22]%2C[%22fd1b33f5-4cc0-4842-8d23-1275b5940d6b%22%2C%22eaef75f8-9dbe-425f-914c-dbd2c01fc00a%22]%2C[%22e2a5d2ce-8957-4d88-ac81-bd3a6827c531%22%2C%22eb356a95-5c10-4974-86ae-cdc68d8fb429%22]%2C[%221bdd9a62-0d6c-432f-8ce8-5b5b141a56aa%22%2C%22b67e11e8-ff31-459e-92b4-b76e49f0cfc4%22]%2C[%22123125a0-6afb-4c91-a6e7-b3061e542070%22%2C%22046ba103-bf2f-4625-b299-b6f2e4759f9c%22]%2C[%221a259873-fa53-4812-bfdb-3b7452feb271%22%2C%223bcf0104-0851-4a4b-b24c-a5b702aa2331%22]%2C[%22508180de-774e-48dc-9b6d-6745b8ffa70c%22%2C%22853666a3-c099-4f6f-b06f-04ba75144ecd%22]%2C[%22ef9d4650-9931-4b0d-8698-dd229e567e5a%22%2C%228116556b-02fb-481b-a1ec-3261d434be95%22]%2C[%22ca47cf88-a0cb-4a16-9e04-3df81a11f5e9%22%2C%223a6a7e44-26bf-4c2e-a511-ea28da77d76c%22]]',
        'kampyleSessionPageCounter': '3',
        '__rtbh.uid': '%7B%22eventType%22%3A%22uid%22%2C%22id%22%3A%22unknown%22%2C%22expiryDate%22%3A%222027-05-06T04%3A48%3A34.160Z%22%7D',
        '__rtbh.lid': '%7B%22eventType%22%3A%22lid%22%2C%22id%22%3A%22o82NyXAueaS0j9ciYJpE%22%2C%22expiryDate%22%3A%222027-05-06T04%3A48%3A34.161Z%22%7D',
        'ttcsid_CA3M1QBC77U4DS3VBL90': '1778042840603::VaR43X3qwdn7aM33_dOH.8.1778042914966.1',
        '_uetsid': '59fd84a0479211f1b44a01b264e34a58|e09v9j|2|g5t|0|2315',
        '_cs_id': '5ada05f1-e502-a285-fe34-4644759f4aaf.1777882932.7.1778042915.1778042841.1745928109.1812046932638.1.x',
        '_cs_s': '5.5.U.9.1778044715231',
        '_cs_s_ctx': 'c%3AH4sIAAAAAAAACsXOQQ6CMBBG4bt04cqxLSpWEuMdiLo1QH%2FSJrSQGQgL492NK4%2Fg9n2b91J9ZJkfEestJqjKnk7OHAp3sMaZ7U%2FvPKhKhXmepNJ6XdedR9fMYRjzrmc96S40i8jCEPIgbrIfcwbo2z2EYprACU07QCiMKYFysMZQil4%2FdU0T7ffuXNpr6i7OlfZ8LDbdpR2wqK0SiMQx1%2BjBDP7fyvsDg%2B0sKTIBAAA%3D',
        '_uetvid': '59fdc2d0479211f185bf9d0138f40a8c|1cs89ot|1778042916181|5|1|bat.bing.com/p/insights/c/l',
        'ttcsid': '1778042840605::ya0gl54Ekwos1eRdd4CW.11.1778042914965.0::1.66532.73885::66348.2.586.810::83660.25.500',
        '_dd_s': 'aid=67595a92-dc92-4620-bc33-7d0394f5ea43&rum=2&id=f4d4deec-038d-4083-9649-c8c0ad51c3c9&created=1778042836004&expire=1778043824859',
        'mobsuccess.com_tag_js_v2_decathlon_0': '{"clickid":null,"actionsOk":{"duration":[true],"nbpages":[]},"duration":61251,"nbpages":5}',
    }

    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'en-US,en;q=0.9',
        'cache-control': 'no-cache',
        'pragma': 'no-cache',
        'priority': 'u=0, i',
        'referer': 'https://www.decathlon.fr/search?Ntt=Timberland',
        'sec-ch-ua': '"Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-ch-viewport-width': '1280',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36',
        'viewport-width': '1280',
        # 'cookie': 'AUTH_STATE=eyJhcHAiOiJXTkYifQ%3D%3D; ecom_user_id=978a1b7e-6473-47fd-b00a-8edeb3cd555b; didomi_token=eyJ1c2VyX2lkIjoiMTlkZjIxM2YtY2VmOC02M2E3LWI3ODktODU4YzBiZDEyNDhjIiwiY3JlYXRlZCI6IjIwMjYtMDUtMDRUMDg6MjE6MjkuNDU1WiIsInVwZGF0ZWQiOiIyMDI2LTA1LTA0VDA4OjIyOjExLjMzM1oiLCJ2ZXJzaW9uIjoyLCJwdXJwb3NlcyI6eyJlbmFibGVkIjpbIm1hcmtldGluZy1NUlpWcHJlYSIsInBlcnNvbmFsaXMtdGY4cFpUVkgiLCJhbmFseXRpY3MtR01nQldHVGgiXX0sInZlbmRvcnMiOnsiZW5hYmxlZCI6WyJnb29nbGUiLCJjOmFkeWVuLVBqYlljR0N6IiwiYzpnb29nbGVwYXktaXRRcVg4a3EiLCJjOnBheXBhbGZyLThHVW1heTRVIiwiYzphcHBsZXBheS15Y0hIQk10UiIsImM6a2xhcm5hLUJrakZoYTRNIiwiYzp2YWxpdXotWEZoeUZhdFUiLCJjOmZhY2Vib29rYS1ReU1ETEdKUSIsImM6YW1wbGl0dWRlLXE2WmZKVExhIiwiYzpiYW1idXNlci1NeE5icFlCVyIsImM6eXNhbmNlLTN4d0Z4OWU3IiwiYzpyYWt1dGVuYWQtd1FkY3JxTm0iLCJjOnZlcml6b25zdC1hY1RCTDlXYiIsImM6cGludGVyZXN0LVZKR0Y5MkZhIiwiYzp0aWt0b2stRTNaMjZwWTgiLCJjOmlkZWFsby1GR0Q2eGVoRSIsImM6cnRiaG91c2UtQmZ0MnA0ZzIiLCJjOmdvb2dsZXJlbS1SWEhoaVhyUiIsImM6dGVhZHMtY1BNVWkyUWUiLCJjOmRlY2F0aGxvbi04TE45aUNjQyIsImM6Z29vZ2xlYWRzLUFrMzJUUERBIiwiYzpiaW5nLW5MaVFMQUNpIiwiYzptb2JzdWNjZXNzLUdEa2VQTGJYIiwiYzpvZ3VyeS1oa0FpekdmbiIsImM6a2Vsa29vLUZaWWNMemgyIiwiYzpiYXRjaHdlYi0yQTd0SHBhQiIsImM6YXRpbnRlcm5lLUNrOXBXaFlFIiwiYzpkeW5hbWljeWktRVRlYXhIY2siLCJjOmNvbnRlbnRzcS1WeFFjTXpwSCIsImM6c3RhdHNpZy1xYmVDMjdCOCIsImM6YWxnb2xpYS1rZDM0eUN4QSIsImM6Y2xvdWZsYXJlLUhOUldyWVp5IiwiYzptZWRhbGxpYS13bUQ4WmY5aCIsImM6ZGVjYXRobG9uLTJWeWI0eXJuIiwiYzpkYXRhZG9nLXdjclY2SEZYIiwiYzpjYWFzdC1ZeWlXUE1xYyJdfSwidmVuZG9yc19saSI6eyJlbmFibGVkIjpbImdvb2dsZSJdfX0=; euconsent-v2=CQjrs8AQjrs8AAHABBENCdFgAP_gAELAAAqIIyQBgAMAAfABUAIQBeYEZALzgBgAqAEIAvMAAAAA.IIyQBgAMAAfABUAIQBeYEZAA.f_wACFgAAAAA; _gcl2_au=1.1.1951575315.1777882931; __ywtfpcvuid=38863374601777882931887; _fbp=fb.1.1777882932123.883126665276478206; _tt_enable_cookie=1; _ttp=01KQS199580RZNW0SRXQ6S11RG_.tt.1; __ywtfpcvuid=38863374601777882931887; __ywtfpcvuid_refresh=1778401332478; _cs_c=0; _pin_unauth=dWlkPU5UTmtPVFF4T0RjdFl6Y3dPUzAwTmpjeUxXRXdNREV0TURFeE9EUmhPVEV4WW1abQ; kampyle_userid=011c-48d4-b827-e274-11a7-6c39-1f11-9620; USER_TOKEN_FOR_ANALYTICS=50a85cc5-68cd-4684-a4aa-7106cd8c591b; _dyid_server=-653020995003066534; _gcl_au=1.1.1767690262.1777882931.1460436215.1777981565.1777981567; cf_clearance=f.LXDSyRtx8voqbczPOW5rxEKV8JWA840zK7XrZ9_lU-1777981984-1.2.1.1-YfYqQrZyuM9A6n9Hpoi51isaEFKXBZ2feJQd4dQ2UpNaf7Evax7EkPO0WywNKKhpiRbqMe5_aEVKPDE5BlCBlAqaX8DyU57dPTcSnn3lEhrzKGOtXy8l8kAc90BwbJCI5BDFG.UqUBIeIeLrVTujocdoiZ2Y2eJO5YvAyovLxfEssHRuLn8Y8UCmIium6qyGJLv0ubiukreg3nX3hSELBBW3m_rmHF_zk7z07YvbS7coc_gyF5Tuc1bc88WJ.AKkCPs0qWHUWAYNBzSYaE6v7xZhwliCTm1Ki6pacF_6v9JswzzTjL6VhEJ2I.qJREWhztJpGwc58w1xqq7kpFbwvg; _dyjsession=z51e4zcit8cpq2wb0p3ap4pazrlydd0a; dkt_ecom_tracking=eyJhbXBsaXR1ZGUiOnsiZGV2aWNlSWQiOiI1ODJjNzc0MC0xNDRhLTQ3NmYtOTE0MS02MmZmZTYyNjQ5ZTkiLCJzZXNzaW9uSWQiOjE3NzgwNDI4MzY2MzV9fQ==; __ywtfpcsuid=22227612341778042839767; _cs_cvars=%7B%7D; tfpsi=0aa04af1-d16a-4bcb-95ec-7829a18946f9; kampyleUserSession=1778042859446; kampyleUserSessionsCount=45; kampyleUserPercentile=81.15545816216752; __cf_bm=sNik2n8nlogKlyoMo0o6thxaoxOYTSk8f3YQM81VuvI-1778042908.6161523-1.0.1.1-0zJ8AySB6DvGUFNRB3OUa1k6HXwwQcgbrT4Ev9Wy.oCDBRmblTQ6B4ulV4cvHCS9hNzUbwxhbno2SG11rJm8BIRv8mXPirfgXMGZfmZTCiCHPGb8IiteAAdhpYDVGDxU; _cfuvid=8OXh6XwYdNgrwRMJcQOApkfljRUOJV_zCgKdCvwbWpw-1778042908.6161523-1.0.1.1-rau.cNs7WAIEqRV6INnc_5D7dF7zQ5Ndh4cT34D5xgw; CUSTOMER_LVP=[[%229a542c73-249b-46a5-8368-6b4286d5297b%22%2C%2238c190df-624c-4b6f-b06d-0ed4f9440826%22]%2C[%22338961%22%2C%22028ffdfc-b8fe-4926-aaf9-f5be6c8bda10%22]%2C[%22fd1b33f5-4cc0-4842-8d23-1275b5940d6b%22%2C%22eaef75f8-9dbe-425f-914c-dbd2c01fc00a%22]%2C[%22e2a5d2ce-8957-4d88-ac81-bd3a6827c531%22%2C%22eb356a95-5c10-4974-86ae-cdc68d8fb429%22]%2C[%221bdd9a62-0d6c-432f-8ce8-5b5b141a56aa%22%2C%22b67e11e8-ff31-459e-92b4-b76e49f0cfc4%22]%2C[%22123125a0-6afb-4c91-a6e7-b3061e542070%22%2C%22046ba103-bf2f-4625-b299-b6f2e4759f9c%22]%2C[%221a259873-fa53-4812-bfdb-3b7452feb271%22%2C%223bcf0104-0851-4a4b-b24c-a5b702aa2331%22]%2C[%22508180de-774e-48dc-9b6d-6745b8ffa70c%22%2C%22853666a3-c099-4f6f-b06f-04ba75144ecd%22]%2C[%22ef9d4650-9931-4b0d-8698-dd229e567e5a%22%2C%228116556b-02fb-481b-a1ec-3261d434be95%22]%2C[%22ca47cf88-a0cb-4a16-9e04-3df81a11f5e9%22%2C%223a6a7e44-26bf-4c2e-a511-ea28da77d76c%22]]; kampyleSessionPageCounter=3; __rtbh.uid=%7B%22eventType%22%3A%22uid%22%2C%22id%22%3A%22unknown%22%2C%22expiryDate%22%3A%222027-05-06T04%3A48%3A34.160Z%22%7D; __rtbh.lid=%7B%22eventType%22%3A%22lid%22%2C%22id%22%3A%22o82NyXAueaS0j9ciYJpE%22%2C%22expiryDate%22%3A%222027-05-06T04%3A48%3A34.161Z%22%7D; ttcsid_CA3M1QBC77U4DS3VBL90=1778042840603::VaR43X3qwdn7aM33_dOH.8.1778042914966.1; _uetsid=59fd84a0479211f1b44a01b264e34a58|e09v9j|2|g5t|0|2315; _cs_id=5ada05f1-e502-a285-fe34-4644759f4aaf.1777882932.7.1778042915.1778042841.1745928109.1812046932638.1.x; _cs_s=5.5.U.9.1778044715231; _cs_s_ctx=c%3AH4sIAAAAAAAACsXOQQ6CMBBG4bt04cqxLSpWEuMdiLo1QH%2FSJrSQGQgL492NK4%2Fg9n2b91J9ZJkfEestJqjKnk7OHAp3sMaZ7U%2FvPKhKhXmepNJ6XdedR9fMYRjzrmc96S40i8jCEPIgbrIfcwbo2z2EYprACU07QCiMKYFysMZQil4%2FdU0T7ffuXNpr6i7OlfZ8LDbdpR2wqK0SiMQx1%2BjBDP7fyvsDg%2B0sKTIBAAA%3D; _uetvid=59fdc2d0479211f185bf9d0138f40a8c|1cs89ot|1778042916181|5|1|bat.bing.com/p/insights/c/l; ttcsid=1778042840605::ya0gl54Ekwos1eRdd4CW.11.1778042914965.0::1.66532.73885::66348.2.586.810::83660.25.500; _dd_s=aid=67595a92-dc92-4620-bc33-7d0394f5ea43&rum=2&id=f4d4deec-038d-4083-9649-c8c0ad51c3c9&created=1778042836004&expire=1778043824859; mobsuccess.com_tag_js_v2_decathlon_0={"clickid":null,"actionsOk":{"duration":[true],"nbpages":[]},"duration":61251,"nbpages":5}',
    }

    db = DB()
    rows = db.fetch_pending_urls("products_links")

    if not rows:
        print("No rows found")
        return

    # split work
    rows = rows[worker_id::total_workers]

    print(f"Worker {worker_id} handling {len(rows)} rows")

    batch_data = []
    processed_urls = []
    BATCH_SIZE = 200

    for color, product_url in rows:
        try:
            data = process_product(color, product_url, headers, cookies, worker_id)

            if data:
                batch_data.append(data)
                processed_urls.append(product_url)

            # 🔥 flush batch
            if len(batch_data) >= BATCH_SIZE:
                db.insert_pdp_batch(batch_data)

                for url in processed_urls:
                    db.cursor.execute(
                        "UPDATE products_links SET status='done' WHERE product_url=%s",
                        (url,)
                    )

                db.conn.commit()

                print(f"[Worker {worker_id}] Inserted & updated {len(batch_data)} records")

                batch_data.clear()
                processed_urls.clear()

        except Exception as e:
            print(f"[Worker {worker_id}] Error: {e}")

    # 🔥 final flush (remaining records)
    if batch_data:
        db.insert_pdp_batch(batch_data)

        for url in processed_urls:
            db.cursor.execute(
                "UPDATE products_links SET status='done' WHERE product_url=%s",
                (url,)
            )

        db.conn.commit()

        print(f"[Worker {worker_id}] Final insert {len(batch_data)} records")

    db.close()



if __name__ == "__main__":

        worker_id = int(sys.argv[1]) if len(sys.argv) > 1 else 0
        total_workers = int(sys.argv[2]) if len(sys.argv) > 2 else 1

        parse(worker_id, total_workers)