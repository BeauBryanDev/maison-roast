
from django.contrib.auth import get_user_model
from django.test import TestCase

from orders.models import Order
from products.models import Product
from products.test_utils import make_product

from .tools import TOOL_SCHEMAS, dispatch
from .tools.create_order import create_order
from .tools.menu import check_product_availability, get_product_details, search_menu
from .tools.read_orders import read_orders
from users.test_utils import ADULT_DOB

User = get_user_model()


class _Anon:
    is_authenticated = False


class MenuToolsTestCase(TestCase):
    def setUp(self):
        self.latte = make_product(
            'Coffee', 'Milky',
            name='Vanilla Latte', description='Sweet and milky',
            price='3.80', stock=10)
        self.sold_out = make_product(
            'Dessert',
            name='Tiramisu', description='Classic',
            price='5.90', stock=0)
        self.hidden = make_product(
            'Coffee',
            name='Secret Blend', description='Not on sale',
            price='9.00', stock=5, available=False)

    def test_search_by_keyword(self):
        result = search_menu(query='latte')
        self.assertEqual(result['count'], 1)
        self.assertEqual(result['results'][0]['name'], 'Vanilla Latte')

    def test_search_by_category(self):
        result = search_menu(category='Dessert')
        self.assertEqual([r['name'] for r in result['results']], ['Tiramisu'])

    def test_search_with_no_match_is_empty_not_an_error(self):
        result = search_menu(query='sushi')
        self.assertEqual(result['count'], 0)
        self.assertEqual(result['results'], [])

    def test_limit_is_clamped(self):
        result = search_menu(limit=9999)
        self.assertLessEqual(result['count'], 25)

    def test_bad_limit_falls_back_to_default(self):
        self.assertIn('count', search_menu(limit='lots'))

    def test_out_of_stock_reports_unavailable(self):
        result = get_product_details(self.sold_out.id)
        self.assertFalse(result['is_available'])

    def test_unavailable_flag_reports_unavailable(self):
        result = get_product_details(self.hidden.id)
        self.assertFalse(result['is_available'])

    def test_details_omit_ingredients_and_allergens(self):
        # Deviation 2: the fields do not exist, so the keys are absent rather
        # than present and empty, which would read as "no allergens".
        result = get_product_details(self.latte.id)
        self.assertNotIn('ingredients', result)
        self.assertNotIn('allergens', result)

    def test_details_for_missing_product_is_an_error_not_an_exception(self):
        self.assertIn('error', get_product_details(999999))

    def test_availability_by_name(self):
        result = check_product_availability(product_name='vanilla latte')
        self.assertTrue(result['exists'])
        self.assertTrue(result['is_available'])

    def test_availability_for_unknown_name(self):
        result = check_product_availability(product_name='unicorn tears')
        self.assertFalse(result['exists'])
        self.assertFalse(result['is_available'])

    def test_availability_needs_an_argument(self):
        self.assertIn('error', check_product_availability())

    def test_availability_matches_a_cnn_label_with_accents(self):
        # vision_identify returns `creme_brulee`; the row is "Creme Brulee".
        make_product('Dessert', name='Cr\u00e8me Br\u00fbl\u00e9e',
                     description='Burnt cream', price='4.95', stock=10)
        result = check_product_availability(product_name='creme brulee')
        self.assertTrue(result['exists'])
        self.assertEqual(result['product']['name'], 'Cr\u00e8me Br\u00fbl\u00e9e')

    def test_availability_matches_a_cnn_label_split_by_an_underscore(self):
        # `cup_cakes` arrives as "cup cakes"; the row is "Cupcakes".
        make_product('Dessert', name='Cupcakes', description='Iced',
                     price='3.25', stock=10)
        result = check_product_availability(product_name='cup cakes')
        self.assertTrue(result['exists'])
        self.assertEqual(result['product']['name'], 'Cupcakes')

    def test_search_query_folds_accents(self):
        make_product('Dessert', name='Crème Brûlée',
                     description='Burnt cream', price='4.95', stock=10)
        result = search_menu(query='creme brulee')
        self.assertEqual([r['name'] for r in result['results']],
                         ['Crème Brûlée'])

    def test_search_query_folds_an_underscored_label(self):
        make_product('Dessert', name='Cupcakes', description='Iced',
                     price='3.25', stock=10)
        result = search_menu(query='cup_cakes')
        self.assertEqual([r['name'] for r in result['results']], ['Cupcakes'])

    def test_search_fold_does_not_rescue_an_unmatched_category(self):
        # An unknown category must stay empty, not be refilled by the fold.
        result = search_menu(query='tiramisu', category='drinks')
        self.assertEqual(result['count'], 0)
        self.assertIn('note', result)

    def test_folded_matching_does_not_invent_a_product(self):
        self.assertFalse(
            check_product_availability(product_name='creme brulee')['exists'])


class CreateOrderToolTestCase(TestCase):
    """The tool must not be a way around the checkout invariants."""

    def setUp(self):
        self.user = User.objects.create_user(gender='MALE', date_of_birth=ADULT_DOB, 
            username='buyer', password='pw', email='buyer@example.com')
        self.product = Product.objects.create(
            name='Flat White', description='Silky',
            price='4.50', stock=5)

    def test_order_is_created_at_the_catalog_price(self):
        result = create_order(self.user, self.product.id, quantity=2)

        self.assertNotIn('error', result)
        order = Order.objects.get(order_number=result['order_number'])
        line = order.product_orders.get()
        self.assertEqual(str(line.price_per_item), '4.50')
        self.assertEqual(str(order.total), '9.00')

    def test_stock_is_decremented_once(self):
        create_order(self.user, self.product.id, quantity=2)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)

    def test_anonymous_is_refused(self):
        result = create_order(_Anon(), self.product.id, quantity=1)
        self.assertIn('error', result)
        self.assertEqual(Order.objects.count(), 0)

    def test_quantity_below_one_is_refused(self):
        result = create_order(self.user, self.product.id, quantity=0)
        self.assertIn('error', result)
        self.assertEqual(Order.objects.count(), 0)

    def test_more_than_stock_is_refused(self):
        result = create_order(self.user, self.product.id, quantity=99)
        self.assertIn('error', result)
        self.assertEqual(Order.objects.count(), 0)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)

    def test_unavailable_product_is_refused(self):
        self.product.available = False
        self.product.save()

        result = create_order(self.user, self.product.id, quantity=1)

        self.assertIn('error', result)
        self.assertEqual(Order.objects.count(), 0)

    def test_user_without_email_is_refused(self):
        emailless = User.objects.create_user(gender='MALE', date_of_birth=ADULT_DOB, username='noemail', password='pw', email='')
        result = create_order(emailless, self.product.id, quantity=1)
        self.assertIn('error', result)
        self.assertEqual(Order.objects.count(), 0)

    def test_missing_product_is_an_error(self):
        self.assertIn('error', create_order(self.user, 999999, quantity=1))


class ReadOrdersToolTestCase(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(gender='MALE', date_of_birth=ADULT_DOB, 
            username='alice', password='pw', email='a@example.com')
        self.bob = User.objects.create_user(gender='MALE', date_of_birth=ADULT_DOB, 
            username='bob', password='pw', email='b@example.com')
        self.product = Product.objects.create(
            name='Espresso', description='Short', price='2.50', stock=50)
        create_order(self.alice, self.product.id, quantity=1)
        create_order(self.bob, self.product.id, quantity=2)

    def test_returns_only_the_callers_orders(self):
        result = read_orders(self.alice)
        self.assertEqual(result['count'], 1)
        self.assertEqual(result['orders'][0]['items'][0]['quantity'], 1)

    def test_anonymous_is_refused(self):
        self.assertIn('error', read_orders(_Anon()))

    def test_soft_deleted_orders_are_hidden(self):
        Order.objects.filter(user=self.alice).update(is_active=False)
        self.assertEqual(read_orders(self.alice)['count'], 0)

    def test_no_fulfilment_status_is_reported(self):
        # There is no status field on Order; Basil must not imply it knows one.
        payload = read_orders(self.alice)['orders'][0]
        self.assertNotIn('status', payload)


class DispatchTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(gender='MALE', date_of_birth=ADULT_DOB, 
            username='u', password='pw', email='u@example.com')
        Product.objects.create(
            name='Mocha', description='Chocolatey', price='4.00', stock=3)

    def test_schemas_and_handlers_agree(self):
        from .tools import _HANDLERS
        self.assertEqual({s['name'] for s in TOOL_SCHEMAS}, set(_HANDLERS))

    def test_unknown_tool_returns_an_error(self):
        self.assertIn('error', dispatch('drop_database', {}))

    def test_bad_arguments_do_not_raise(self):
        self.assertIn('error', dispatch('get_product_details', {'wrong': 1}))

    def test_user_is_injected_not_taken_from_the_model(self):
        # tool_input comes from the model, so a user named there must be
        # discarded in favour of the real caller.
        other = User.objects.create_user(gender='MALE', date_of_birth=ADULT_DOB, 
            username='other', password='pw', email='other@example.com')
        product = Product.objects.get(name='Mocha')
        create_order(other, product.id, quantity=1)

        result = dispatch('read_orders', {'user': other}, user=self.user)

        self.assertNotIn('error', result)
        self.assertEqual(result['count'], 0)  # self.user has no orders


class CategoryFilterTestCase(TestCase):
    """Categories are an M2M now: one product is several things at once."""

    def setUp(self):
        self.iced_latte = make_product(
            'Coffee', 'Iced', 'Espresso', 'Milky',
            name='Iced Latte', description='Cold and milky', price='5.25', stock=8)
        self.muffin = make_product(
            'Pastry', name='Blueberry Muffin', description='Baked', price='3.49', stock=4)

    def test_a_product_is_found_under_every_category_it_has(self):
        for category in ['Coffee', 'Iced', 'Espresso', 'Milky']:
            with self.subTest(category=category):
                names = [r['name'] for r in search_menu(category=category)['results']]
                self.assertIn('Iced Latte', names)

    def test_a_category_it_does_not_have_excludes_it(self):
        names = [r['name'] for r in search_menu(category='Pastry')['results']]
        self.assertNotIn('Iced Latte', names)

    def test_an_invented_category_returns_nothing_and_names_the_real_ones(self):
        """Handing back the whole menu would read as 'these all match' -- a
        muffin offered as a drink."""
        result = search_menu(category='drinks')

        self.assertEqual(result['count'], 0)
        self.assertIn('No category called "drinks"', result['note'])
        self.assertIn('Coffee', result['note'])

    def test_a_near_miss_still_finds_products(self):
        """'espresso ' or 'coffee' cased differently should not dead-end."""
        result = search_menu(category='coff')
        self.assertTrue(result['count'])

    def test_serialised_products_carry_every_category(self):
        result = search_menu(query='Iced Latte')
        self.assertCountEqual(result['results'][0]['categories'],
                              ['Coffee', 'Iced', 'Espresso', 'Milky'])
