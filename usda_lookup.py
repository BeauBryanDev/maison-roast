
import json
import os
import sys
import time
 
import requests
 
USDA_API_KEY = os.environ["USDA_API_KEY"]
BASE_URL = "https://api.nal.usda.gov/fdc/v1"
 
# Search across all data types, ordered roughly by how likely they are to
# match a prepared café/patisserie dish rather than a raw ingredient.
# Foundation/SR Legacy are mostly raw ingredients (flour, sugar), Survey
# (FNDDS) is "food as eaten" -- usually the best fit for a finished dish --
# and Branded is manufacturer-labeled packaged products.
DATA_TYPES = ["Survey (FNDDS)", "Branded", "SR Legacy", "Foundation"]

CANDIDATES_PER_CLASS = 3
REQUEST_DELAY_SECONDS = 0.5  # polite pacing; far under the 1,000/hr key limit
MAX_ATTEMPTS = 4
OUT_PATH = "food_nutrition_raw.json"
FNDDS_OUT_PATH = "food_nutrition_FNDDS.json"
FNDDS_CANDIDATES = 5

# FNDDS uses its own vocabulary; the class name alone finds nothing or junk.
FNDDS_QUERIES = {
    "croque_madame": "ham sandwich on white with cheese",
    "donuts": "doughnut",
    "omelette": "omelet",
    "pizza": "cheese pizza",
    "cheese_plate": "cheese",
    "cup_cakes": "cupcake with icing",
    "pancakes": "pancakes plain",
    "french_toast": "french toast plain",
    "frozen_yogurt": "frozen yogurt vanilla",
}

# Mixed-source classes whose main results were all wrong dishes.
FNDDS_EXTRA = ["cheese_plate", "cup_cakes", "pancakes", "french_toast", "frozen_yogurt"]
 
# USDA nutrient numbers. These are stable IDs across the whole database --
# the same four numbers whether the food is a banana or a branded muffin.
NUTRIENT_IDS = {
    "calories_kcal": 1008,   # Energy, kcal
    "protein_g": 1003,       # Protein
    "carbs_g": 1005,         # Carbohydrate, by difference
    "fat_g": 1004,           # Total lipid (fat)
}
 
MENU_CLASSES = [
    "apple_pie", "baklava", "beignets", "bread_pudding", "breakfast_burrito",
    "bruschetta", "brownie","caesar_salad", "cannoli", "carrot_cake", "cheese_plate",
    "cheesecake", "chocolate_cake", "chocolate_mousse", "churros",
    "club_sandwich", "creme_brulee", "croque_madame", "cup_cakes",
    "deviled_eggs", "donuts", "eggs_benedict", "french_onion_soup",
    "french_toast", "frozen_yogurt", "garlic_bread", "greek_salad",
    "grilled_cheese_sandwich", "hamburger", "hot_dog", "ice_cream","muffin",
    "lasagna", "macarons", "omelette", "pancakes", "panna_cotta", "pizza",
    "red_velvet_cake", "strawberry_shortcake", "tiramisu", "waffles",
]
 
 
class SearchError(Exception):
    pass


def search_food(query, data_types=DATA_TYPES, 
                page_size=CANDIDATES_PER_CLASS):
    # POST, not GET: the GET form intermittently returns an nginx 400 for the
    # same query that succeeds a moment later. Retries cover what remains.
    body = {
        "query": query.replace("_", " "),
        "pageSize": page_size,
        "dataType": data_types,
    }
    status = None
    
    for attempt in range(MAX_ATTEMPTS):
        
        try:
            resp = requests.post(
                f"{BASE_URL}/foods/search",
                params={"api_key": USDA_API_KEY},
                json=body,
                timeout=15,
            )
            status = resp.status_code
            
            if resp.ok:
                return resp.json().get("foods", [])
            
        except requests.RequestException as exc:
            status = type(exc).__name__
            
        time.sleep(2 ** attempt)
        
    # The key rides in the URL, so never put the URL in the error.
    raise SearchError(f"failed after {MAX_ATTEMPTS} attempts (last: {status})")
 
 
def extract_nutrients(food):
    """Pull the four macros we care about, keyed by our own field names.
 
    FDC nutrient numbers are consistent across search results, but the field
    name used to hold them differs by data type (foodNutrients here uses
    'nutrientId' + 'value' in the search endpoint's shape).
    """
    values = {name: None for name in NUTRIENT_IDS}
    
    for nutrient in food.get("foodNutrients", []):
        
        nutrient_id = nutrient.get("nutrientId")
        
        for field_name, target_id in NUTRIENT_IDS.items():
            
            if nutrient_id == target_id:
                
                values[field_name] = nutrient.get("value")
                
    return values
 
 
def build_candidate(food):
    
    return {
        "fdc_id": food.get("fdcId"),
        "description": food.get("description"),
        "data_type": food.get("dataType"),
        "brand_owner": food.get("brandOwner"),  # populated only for Branded
        "serving_size": food.get("servingSize"),
        "serving_size_unit": food.get("servingSizeUnit"),
        **extract_nutrients(food),
    }
 
 
def load_existing():
    """Keep finished classes (and any chosen_index already set) across reruns."""
    try:
        with open(OUT_PATH, encoding="utf-8") as f:
            
            return json.load(f)
        
    except (FileNotFoundError, json.JSONDecodeError):
        
        return {}


def main():
    results = load_existing()
    
    for i, label in enumerate(MENU_CLASSES, start=1):
        
        if results.get(label, {}).get("candidates"):
            continue
        
        print(f"[{i}/{len(MENU_CLASSES)}] searching: {label}")
        try:
            foods = search_food(label)
            
        except SearchError as exc:
            print(f"  ERROR: {exc}")
            results[label] = {"error": str(exc), "candidates": []}
            time.sleep(REQUEST_DELAY_SECONDS)
            continue
 
        candidates = [build_candidate(f) for f in foods]
        results[label] = {"candidates": candidates, "chosen_index": None}
 
        if not candidates:
            
            print("  no results found")
            
        else:
            
            for idx, c in enumerate(candidates):
                
                print(f"  [{idx}] {c['data_type']:10s} {c['description'][:60]!r} "
                      f"kcal={c['calories_kcal']}")
 
        time.sleep(REQUEST_DELAY_SECONDS)
 
    results = {label: results[label] for label in MENU_CLASSES if label in results}
    
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        
        json.dump(results, f, indent=2, ensure_ascii=False)

    failed = [k for k, v in results.items() if v.get("error")]
    
    print(f"\nWrote {len(results)} classes to {OUT_PATH} ({len(failed)} failed)")
    
    if failed:
        print("Rerun to retry only these: " + ", ".join(failed))
    print("Next: review each entry, set 'chosen_index' to the best candidate "
          "(or -1 to skip / hand-write your own values), and adjust macros "
          "as needed for a vintage café-scale portion before Stage C.")
 
 
def fndds_pass():
    """Search FNDDS alone for every class whose main results are all Branded.

    FNDDS is "food as eaten" with no brand behind it, a better fit for a
    café dish than one manufacturer's label.
    """
    raw = load_existing()
    
    labels = [k for k, v in raw.items()
              
              if v.get("candidates")
              and all(c["data_type"] == "Branded" for c in v["candidates"])]
    
    labels += [k for k in FNDDS_EXTRA if k not in labels]
    results = {}
    
    for i, label in enumerate(labels, start=1):
        
        print(f"[{i}/{len(labels)}] FNDDS: {label}")
        
        try:
            foods = search_food(FNDDS_QUERIES.get(label, label),
                                ["Survey (FNDDS)"], 
                                FNDDS_CANDIDATES)
            
        except SearchError as exc:
            
            print(f"  ERROR: {exc}")
            results[label] = {"error": str(exc), "candidates": []}
            
        else:
            candidates = [build_candidate(f) for f in foods]
            results[label] = {"candidates": candidates, "chosen_index": None}
            
            for idx, c in enumerate(candidates):
                print(f"  [{idx}] {c['description'][:60]!r} kcal={c['calories_kcal']}")
                
        time.sleep(REQUEST_DELAY_SECONDS)

    with open(FNDDS_OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
        
    print(f"\nWrote {len(results)} classes to {FNDDS_OUT_PATH}")



if __name__ == "__main__":
    
    
    fndds_pass() if "--fndds" in sys.argv else main()
