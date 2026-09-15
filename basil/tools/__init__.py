# Tool registry: schemas sent to the model, and server-side dispatch.

# Tools never raise to the agent. Failures come back as {"error": ...} so Basil
# can tell the user plainly what went wrong.

from .check_compliance import check_compliance
from .create_order import create_order
from .knowledge import search_knowledge_base
from .menu import check_product_availability, get_product_details, search_menu
from .read_orders import read_orders
from .vision import vision_identify
from .check_nutrition_info import get_nutrition_info

import logging

logger = logging.getLogger(__name__)

# Tools needing the caller's identity get it injected by dispatch, not from the
# model. Basil cannot choose whose orders it reads.
_NEEDS_USER = {'create_order', 'read_orders', 'check_compliance'}

# Scoped to the caller's own chat session, so one visitor cannot classify another's upload.
_NEEDS_SESSION = {'vision_identify'}

TOOL_SCHEMAS = [
    {
        'name': 'search_menu',
        'description': (
            'Search the coffee shop menu by keyword and/or category. Use this '
            'for anything about what is on the live menu.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'query': {'type': 'string', 'description': 'Keyword to search for.'},
                'category': {'type': 'string', 'description': (
                    'One category name. The valid names are listed in the '
                    'system prompt; a product belongs to several at once.'
                )},
                'limit': {'type': 'integer', 'description': 'Max results, default 10.'},
            },
        },
    },
    {
        'name': 'get_product_details',
        'description': 'Full details for one product, by id.',
        'input_schema': {
            'type': 'object',
            'properties': {'product_id': {'type': 'integer'}},
            'required': ['product_id'],
        },
    },
    {
        'name': 'check_product_availability',
        'description': 'Whether a product exists on the menu and is orderable now.',
        'input_schema': {
            'type': 'object',
            'properties': {
                'product_id': {'type': 'integer'},
                'product_name': {'type': 'string'},
            },
        },
    },
    {
        'name': 'check_compliance',
        'description': (
            'MANDATORY before offering, confirming or ordering ANY alcoholic '
            'item (menu tools flag these with is_alcohol: true). Checks the '
            "signed-in customer's age and whether the bar is open yet. Call it "
            'every time, before create_order. If may_sell_alcohol is false, do '
            'not place the order — say what the message says, kindly, and '
            'suggest something else.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'product_id': {
                    'type': 'integer',
                    'description': 'The alcoholic product the customer wants, if known.',
                },
            },
        },
    },
    {
        'name': 'create_order',
        'description': (
            'Place an order for one product. Confirm the product and quantity '
            'with the customer before calling this. Requires a signed-in user.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'product_id': {'type': 'integer'},
                'quantity': {'type': 'integer'},
                'customer_notes': {'type': 'string'},
            },
            'required': ['product_id', 'quantity'],
        },
    },
    {
        'name': 'vision_identify',
        'description': (
            'Identify the food in an image the customer uploaded. Follow up with '
            'the menu tools to say whether we sell it. If is_unknown is true, ask '
            'the customer what they are looking for instead of guessing.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {'image_id': {'type': 'string'}},
            'required': ['image_id'],
        },
    },
    {
        'name': 'search_knowledge_base',
        'description': (
            'Search the shop knowledge base: refund, delivery and cancellation '
            'policies, allergen and cross-contamination information, the brand '
            'story, coffee origins and roasting, and how our recipes are made. '
            'Use this for anything that is not a live menu, price or stock '
            'question. Quote what comes back rather than answering from memory.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'query': {'type': 'string',
                          'description': "The customer's question, in full."},
                'top_k': {'type': 'integer',
                          'description': 'Passages to return, default 4.'},
            },
            'required': ['query'],
        },
    },
    {
        'name': 'read_orders',
        'description': (
            "The signed-in customer's own recent orders. Says what was bought, "
            'not where the delivery is.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {'limit': {'type': 'integer'}},
        },
    },
    {
        'name': 'get_nutrition_info',
        'description': (
            'Calories, protein, carbs and fat for a menu item, reported per '
            '100g. Use when a customer asks about calories, macros, or '
            'nutrition -- never estimate these yourself. If nothing is on '
            'file, say so rather than guessing a number.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'product_id': {'type': 'integer'},
                'product_name': {'type': 'string'},
            },
        },
    },
    
]

# tools dictionary
_HANDLERS = {
    'search_menu': search_menu,
    'get_product_details': get_product_details,
    'check_product_availability': check_product_availability,
    'check_compliance': check_compliance,
    'create_order': create_order,
    'read_orders': read_orders,
    'vision_identify': vision_identify,
    'search_knowledge_base': search_knowledge_base,
    "get_nutrition_info": get_nutrition_info,
}


# THIS IS THE TOOL HANDLER FOR BASIL
def dispatch(name, tool_input, user=None, session=None):
    """Run a tool by name. Always returns a dict, never raises."""
    handler = _HANDLERS.get(name)
    
    if handler is None:
        return {'error': f'Unknown tool: {name}'}

    kwargs = dict(tool_input or {})
    
    if name in _NEEDS_USER:
        kwargs['user'] = user
        
    if name in _NEEDS_SESSION:
        kwargs['session'] = session

    try:
        return handler(**kwargs)
    
    except TypeError as exc:
        logger.warning(f'Bad arguments for {name}: {exc}')
        return {'error': f'{name} received invalid input.'}
    
    except Exception as exc:
        logger.exception(f'{name} crashed')
        return {'error': f'{name} is temporarily unavailable.'}
