from textwrap import indent

import requests
from curl_cffi import requests as curl_requests
from lxml import html
import json
import re
from parsel import Selector


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

    print(f"Total reviews: {total_reviews}")
    print(f"Distribution: {distribution_counts}")

    return distribution_counts

def extract_breadcrumbs(json_data):
    breadcrumbs = []

    # -------- FIND BREADCRUMBS SAFELY --------
    for item in json_data:
        if isinstance(item, dict) and "breadcrumbs" in item:
            breadcrumbs = item.get("breadcrumbs", [])
            break
        if isinstance(item, list):
            for sub in item:
                if isinstance(sub, dict) and "breadcrumbs" in sub:
                    breadcrumbs = sub.get("breadcrumbs", [])
                    break

    # -------- BUILD L1, L2, L3 DICT --------
    levels = {}

    if isinstance(breadcrumbs, list):
        for i, item in enumerate(breadcrumbs):
            if isinstance(item, dict):
                name = item.get("name")
                if name:
                    levels[f"l{i+1}"] = name

    return levels

def parse():
        cookies = {
            'AUTH_STATE': 'eyJhcHAiOiJXTkYifQ%3D%3D',
            'ecom_user_id': '978a1b7e-6473-47fd-b00a-8edeb3cd555b',
        }

        headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'accept-language': 'en-US,en;q=0.9',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36',
        }

        session = curl_requests.Session(impersonate="chrome124")
        # db = DB()
        # rows=db.fetch_pending_urls("products_links")

        response = session.get(
            "https://www.decathlon.fr/p/mp/timberland/bottines-impermeables-timberland-premium-6/_/R-p-66f341fb-494d-4896-8d1b-76a2f71a3a13",
            cookies=cookies,
            headers=headers,

        )
        #breadcrumps



        print(f"Response OK: {response.ok}")

        if response.ok:
            tree = html.fromstring(response.text)
            paragraphs = tree.xpath('//div[@class="product-info-item__description-marketplace"]//p/text()')  
            description = ' '.join(paragraphs)  # 
            
            print(description)
          
            # bread = tree.xpath(
            #     '//div[@data-cs-override-id="product-header_breadcrumbs"]//script[@type="application/ld+json"]/text()')
            # if bread:
            #     cate_data = json.loads(bread[0])  # Get first script tag content

            #     categories = []
            #     # Iterate over itemListElement
            #     for item in cate_data.get("itemListElement", []):
            #         name = item.get("name", "")
            #         # Skip "Home" (position 1)
            #         if name and name.lower() != "home":
            #             categories.append(name)

            #     # Convert to L1, L2 format
            #     category_hierarchy = {}
            #     for i, name in enumerate(categories, 1):
            #         category_hierarchy[f"l{i}"] = name

            #     print(category_hierarchy)


            #     # Get script with itemGroup
            # script = tree.xpath('string(//script[contains(text(), "self.__next_f.push") and contains(text(), "itemGroup")])')

            # # Get script with translations for return policy
            # return_policy_script = tree.xpath('string(//script[contains(text(), "self.__next_f.push") and contains(text(), "translations")])')

            # if not script:
            #     print("No script found with itemGroup")
            #     return

            # # Clean and parse the main script
            # json_data = clean_json_data(script)
            # with open("json_data.json", "w", encoding="utf-8") as f:
            #     json.dump(json_data,f,indent=4)
            # if not json_data:
            #     print("Failed to parse main script")
            #     return

            # # Extract return policy data
            # return_policy_data = {}
            # if return_policy_script:
            #     return_data = clean_json_data(return_policy_script)
            #     print(return_data)
            #     if return_data and len(return_data) > 3:
            #         translations = return_data[3].get("translations", {})
            #         product_assurance = translations.get("ProductAssurance", {})
            #         return_policy_data = {
            #             "policy": product_assurance.get("returnWithin30days", ""),
            #             "detail": product_assurance.get("returnDescription3P", "")
            #         }

            # # Extract product info - the structure may vary
            # # Try different paths to find itemGroup
            # product_info = {}

            # # Path 1: json_data[3][3].get("itemGroup", {})
            # if isinstance(json_data, list) and len(json_data) > 3:
            #     if isinstance(json_data[3], list) and len(json_data[3]) > 3:
            #         product_info = json_data[3][3].get("itemGroup", {})

            # # Path 2: Direct itemGroup in the list
            # if not product_info and isinstance(json_data, list):
            #     for item in json_data:
            #         if isinstance(item, dict) and "itemGroup" in item:
            #             product_info = item.get("itemGroup", {})
            #             break
            #         elif isinstance(item, list) and len(item) > 3 and isinstance(item[3], dict):
            #             if "itemGroup" in item[3]:
            #                 product_info = item[3].get("itemGroup", {})
            #                 break

            # if not product_info:
            #     print("Could not find itemGroup in parsed data")
            #     print(f"JSON data structure: {type(json_data)}")
            #     if isinstance(json_data, list):
            #         print(f"List length: {len(json_data)}")
            #     return

            # skugrp = product_info.get("skuGroups", [])
            # model_id=skugrp[0].get("modelId")
            # print(model_id)

            # if not skugrp:
            #     print("No skuGroups found")
            #     return

            # temp_data = {}

            # # Product name
            # skus_list = skugrp[0].get("skus", [])

            # if skus_list:
            #     temp_data["category_hirerchy"]=extract_breadcrumbs(json_data)
            #     temp_data["product_name"] = skus_list[0].get("title") if skus_list else None

            # # IDs
            # temp_data["product_id"] = product_info.get("id")
            # sku_id=product_info.get("representativeSku")

            # temp_data["sku_id"] = sku_id

            # #page save

            # # Price, MRP, Discount
            # if skus_list:
            #     offers = skus_list[0].get("offers", [{}])[0]
            #     fixed_prices = offers.get("fixedPrices", [{}])[0]
            #     type_targets = fixed_prices.get("typeTargets", [{}])[0]
            #     currencies = type_targets.get("currencies", {})
            #     main_currency = currencies.get("main", {})

            #     # Get MRP and selling price
            #     mrp = main_currency.get("referenceValueWithTaxes")
            #     selling_price = main_currency.get("valueWithTaxes")
            #     disc_per=main_currency.get("discountPercentage")
            #     # If MRP is not available, use selling price as MRP
            #     if not mrp or mrp == "null" or mrp is None:
            #         temp_data["mrp"] = selling_price
            #     else:
            #         temp_data["mrp"] = mrp

            #     temp_data["selling_price"] = selling_price
            #     temp_data["discount_percentage"] = disc_per if disc_per not in (None, "null", "") else  None

            # # Images
            # if skus_list:
            #     images = skus_list[0].get("images", [])
            #     temp_data["images"] = [image.get("url") for image in images if image.get("url")]

            # # Colors
            # if skus_list:
            #     colors = skus_list[0].get("colors", [])
            #     temp_data["colors"] = colors[0] if colors else None

            # # Sizes and prices
            # temp_data["size"] = []
            # for size in skus_list:
            #     try:
            #         offers = size.get("offers", [{}])[0]
            #         fixed_prices = offers.get("fixedPrices", [{}])[0]
            #         type_targets = fixed_prices.get("typeTargets", [{}])[0]
            #         currencies = type_targets.get("currencies", {})
            #         main_currency = currencies.get("main", {})

            #         temp_size = {
            #             "size": size.get("sizeLabel"),
            #             "price": main_currency.get("valueWithTaxes")
            #         }
            #         temp_data["size"].append(temp_size)
            #     except Exception as e:
            #         print(f"Error extracting size info: {e}")
            #         continue

            # # Reviews
            # reviews = product_info.get("reviews")
            # if reviews and isinstance(reviews, dict):
            #     average=reviews.get("average")
            #     avg_rating = round(average, 1) if average is not None else None
            #     temp_data["reviews_count"] = reviews.get("count")
            #     temp_data["average_review"] =avg_rating
            #     revies_data = fetch_reviews(model_id,sku_id ,headers, cookies)
            #     temp_data["reviews"] = revies_data

            # else:
            #     temp_data["reviews_count"] = None
            #     temp_data["average_review"] = None
            #     temp_data["reviews"] = None

            # # Seller and shipper
            # sku_conditions = skugrp[0].get("skuGroupConditions", [{}])[0]
            # temp_data["seller_name"] = sku_conditions.get("seller", {}).get("name")
            # temp_data["shipped_by"] = sku_conditions.get("fulfiller", {}).get("name")

            # # Short description
            # if skus_list:
            #     temp_data["short_description"] = skus_list[0].get("catchline")

            # # Description
            # desc = skus_list[1].get("description") if len(skus_list) > 1 else skus_list[0].get("description")
            # if desc:
            #     selector = Selector(text=desc)
            #     temp_data["description"] = ''.join(selector.xpath('//text()').extract()).strip()
            # else:
            #     temp_data["description"] = ""

            # temp_data["specifications"] = {"details": {}}

            # if skus_list and isinstance(skus_list[0], dict):

            #     # ---------- DETAILS ----------
            #     for char in skus_list[0].get("characteristics") or []:
            #         if not isinstance(char, dict):
            #             continue

            #         values = char.get("values") or []
            #         if values and isinstance(values[0], dict):

            #             key = char.get("name")
            #             value = values[0].get("name")

            #             if key and value:
            #                 temp_data["specifications"]["details"][key] = value

            #     composition_value = None

            #     for chapter in skus_list[0].get("characteristicsChapters", []) or []:
            #         if not isinstance(chapter, dict):
            #             continue

            #         if chapter.get("name") == "composition":
            #             for char in chapter.get("characteristics", []) or []:
            #                 if not isinstance(char, dict):
            #                     continue

            #                 values = char.get("values") or []
            #                 if not values:
            #                     continue

            #                 val = values[0]

            #                 composition_value = (
            #                     val if isinstance(val, str)
            #                     else val.get("name") if isinstance(val, dict)
            #                     else None
            #                 )

            #                 if composition_value:
            #                     break

            #     # ✅ ONLY set if valid value exists
            #     if composition_value:
            #         temp_data.setdefault("specifications", {})
            #         temp_data["specifications"]["composition"] = composition_value


            #     # ---------- MANUFACTURER ----------
            #     fabricant = skus_list[0].get("manufacturer")

            #     if isinstance(fabricant, dict):

            #         fabricant_data = {
            #             "name": fabricant.get("name"),
            #             "address": fabricant.get("postalAddress"),
            #             "email": fabricant.get("contactAddress")
            #         }

            #         # only attach if meaningful data exists
            #         if any(v not in (None, "", "null") for v in fabricant_data.values()):
            #             temp_data["specifications"]["fabricant"] = fabricant_data

            # # Return policy
            # temp_data["return_policy"] = return_policy_data

            # # print(json.dumps(temp_data, indent=2, ensure_ascii=False))

            # with open("sample.json", "w", encoding="utf-8") as f:
            #     json.dump(temp_data, f, indent=4, ensure_ascii=False)

            # print("Data saved to sample.json")

        else:
            print(f"Request failed with status: {response.status_code}")

if __name__=="__main__":
    parse()