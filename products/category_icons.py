
# Static mapping from Category.name to its icon filename under
# static/icons/. A plain dict, not a DB column because it's not editable.


CATEGORY_ICONS = {
    "Alcohol": "alcohol.svg",
    "Bakery": "Bakery.svg",
    "Breakfast": "Breakfast.svg",
    "Coffee": "coffee_cup3.svg",
    "Dessert": "dessert.svg",
    "Drinks": "drinks.svg",
    "Espresso": "espresso.svg",
    "Hot": "hot_drink.svg",
    "Iced": "Iced.svg",
    "Light_Meals": "Light_Meals.svg",
    "Milky": "milky.svg",
    "Non-Coffee": "ice_cream.svg",  # shares the Drinks icon, intentional
    "Pastry": "pastry.svg",
    "Savory_Bites": "Savory_Bites.svg",
    "Sweets_Desserts": "Sweets_Desserts.svg",
    "Wine": "wine.svg",
    "Bread": "bread.svg",
    "Cheese_Plate": "cheese_piece.svg",  
}
# Fallback for any category not in the dict above (new category added via
# admin before someone assigns it a real icon).
DEFAULT_ICON = "coffee_cup3.svg"
 
 
def get_category_icon(category_name):
    return CATEGORY_ICONS.get(category_name, DEFAULT_ICON)
 
 
 