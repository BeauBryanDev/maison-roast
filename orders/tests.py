from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext

from .views import MyOrderList
from .models import Order, ProductOrder
from products.models import Product
from django.contrib.auth.models import AnonymousUser

from basil.tools.create_order import create_order
from products.test_utils import make_product
from users.test_utils import ADULT_DOB, adult_dob, make_minor, make_user
from .services import OrderError, is_age_restricted, place_order

User = get_user_model()

class OrderTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(gender='MALE', date_of_birth=ADULT_DOB, 
            username="testuser_order",
            password="testpassword",
            email="test@example.com"
        )
        self.product = Product.objects.create(
            name="Test Product",
            description="Test Description",
            price=10.00,
            stock=10,
            product_image="https://example.com/test.jpg"
        )
        self.order = Order.objects.create(
            user=self.user,
            order_number="1234567890",
            customer_name="Test Customer",
            customer_email="test@example.com",
            is_active=True,
        )
        self.product_order = ProductOrder.objects.create(
            order=self.order,
            product=self.product,
            quantity=1,
            price_per_item=10.00,
        )

    def test_order_str(self):
        self.assertEqual(str(self.order), "Order 1234567890 -True by Test Customer")

    def test_product_order_str(self):
        # ProductOrder __str__: f"{self.quantity} x {self.product} for Order {self.order.order_number}"
        # Product __str__: f"{self.name} - ${self.price} - Stock: {self.stock}"
        expected_str = f"1 x Test Product - $10.00 - Stock: 10 for Order 1234567890"
        self.assertEqual(str(self.product_order), expected_str)

    def test_order_list_view(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("order_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.order.order_number)
        
            
    def test_order_detail_view(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("order_details", args=[self.order.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.order.order_number)


class MyOrderViewTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(gender='MALE', date_of_birth=ADULT_DOB, 
            username="testuser",
            password="testpassword",
            email="user@test.com"
        )
        self.product = Product.objects.create(
            name="Test Product",
            description="Test Description",
            price=10.00,
            stock=10,
            product_image="https://example.com/test.jpg"
        )
        self.order = Order.objects.create(
            user=self.user,
            order_number="1234567890",
            customer_name="Test Customer",
            customer_email="test@example.com",
            is_active=True,
        )
        self.product_order = ProductOrder.objects.create(
            order=self.order,
            product=self.product,
            quantity=1,
            price_per_item=10.00,
        )
        self.my_order_view = MyOrderList.as_view()

    def test_my_order_view(self):
        self.client.login(username="testuser", password="testpassword")
        response = self.client.get(reverse("order_list")) # Assuming order_list is the name for my_order_view
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.order.order_number)


class OrderDetailQueryCountTestCase(TestCase):
    """order_detail.html walks the line items three times and follows a FK on
    each row, so the detail view must prefetch or the page cost grows with the
    size of the order."""

    def setUp(self):
        self.user = User.objects.create_user(gender='MALE', date_of_birth=ADULT_DOB, 
            username="shopper", password="testpassword", email="shopper@example.com",
        )

    def _order_with_line_items(self, order_number, count):
        order = Order.objects.create(
            user=self.user,
            order_number=order_number,
            customer_name="Shopper",
            customer_email="shopper@example.com",
            is_active=True,
        )
        for i in range(count):
            product = Product.objects.create(
                name=f"{order_number} item {i}",
                description="d",
                price=1.00 + i,
                stock=10
            )
            ProductOrder.objects.create(
                order=order, product=product, quantity=1, price_per_item=product.price,
            )
        return order

    def test_query_count_does_not_grow_with_line_items(self):
        small = self._order_with_line_items("Q-SMALL", 2)
        large = self._order_with_line_items("Q-LARGE", 10)
        self.client.force_login(self.user)

        with CaptureQueriesContext(connection) as small_queries:
            self.client.get(reverse("order_details", args=[small.pk]))

        with CaptureQueriesContext(connection) as large_queries:
            self.client.get(reverse("order_details", args=[large.pk]))

        # Asserting equality rather than a fixed number: the absolute count can
        # shift with middleware, but it must never scale with the order size.
        self.assertEqual(
            len(small_queries),
            len(large_queries),
            f"query count scales with line items "
            f"({len(small_queries)} for 2 items vs {len(large_queries)} for 10) "
            f"-- the prefetch_related on OrderDetail.get_queryset is missing",
        )


class OrderMoneyTestCase(TestCase):
    """Money must never be rounded for display.

    The old order detail template used {% widthratio %} for line subtotals,
    which returns an integer: $2.99 x 2 rendered as "$6".
    """

    def setUp(self):
        self.user = User.objects.create_user(gender='MALE', date_of_birth=ADULT_DOB, 
            username="accountant", password="testpassword", email="acc@example.com",
        )
        self.order = Order.objects.create(
            user=self.user, order_number="MONEY-1", customer_name="Acc",
            customer_email="acc@example.com", is_active=True,
        )
        self.p1 = Product.objects.create(name="Money Latte", description="d",
                                         price="2.99", stock=9)
        self.p2 = Product.objects.create(name="Money Tart", description="d",
                                         price="5.90", stock=9)
        ProductOrder.objects.create(order=self.order, product=self.p1,
                                    quantity=2, price_per_item=self.p1.price)
        ProductOrder.objects.create(order=self.order, product=self.p2,
                                    quantity=3, price_per_item=self.p2.price)

    def test_line_subtotal_is_exact(self):
        lines = {l.product.name: l.subtotal for l in self.order.product_orders.all()}
        self.assertEqual(str(lines["Money Latte"]), "5.98")
        self.assertEqual(str(lines["Money Tart"]), "17.70")

    def test_order_total_is_the_sum(self):
        self.assertEqual(str(self.order.total), "23.68")

    def test_detail_page_shows_exact_money(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("order_details", args=[self.order.pk]))
        self.assertContains(response, "5.98")
        self.assertContains(response, "23.68")
        self.assertNotContains(response, "$6 ")  # the old rounded rendering


class OrderListQueryCountTestCase(TestCase):
    """order_list.html shows each order's item count and total, so the list view
    must prefetch or it costs a query per order."""

    def setUp(self):
        self.user = User.objects.create_user(gender='MALE', date_of_birth=ADULT_DOB, 
            username="lister", password="testpassword", email="lister@example.com",
        )

    def _orders(self, count):
        # order_number is unique, so keep a running offset across calls.
        start = Order.objects.count()
        for n in range(start, start + count):
            order = Order.objects.create(
                user=self.user, order_number=f"LIST-{n}", customer_name="L",
                customer_email="lister@example.com", is_active=True,
            )
            product = Product.objects.create(name=f"Item {n}", description="d",
                                             price=2, stock=5)
            ProductOrder.objects.create(order=order, product=product,
                                        quantity=1, price_per_item=product.price)

    def test_query_count_does_not_grow_with_orders(self):
        self._orders(2)
        self.client.force_login(self.user)
        with CaptureQueriesContext(connection) as few:
            self.client.get(reverse("order_list"))

        self._orders(8)
        with CaptureQueriesContext(connection) as many:
            self.client.get(reverse("order_list"))

        self.assertEqual(
            len(few), len(many),
            f"query count scales with order count ({len(few)} for 2 vs "
            f"{len(many)} for 10) -- prefetch_related on MyOrderList is missing",
        )


class CheckoutSecurityTestCase(TestCase):
    """Guard the checkout path against tampered POST data.

    Each test here corresponds to a fixed exploit -- if one starts failing, the
    hole it covers has been reopened.
    """

    def setUp(self):
        self.user = User.objects.create_user(gender='MALE', date_of_birth=ADULT_DOB, 
            username="buyer",
            password="testpassword",
            email="buyer@example.com",
        )
        self.product = Product.objects.create(
            name="Checkout Test Product",
            description="Test Description",
            price="2.99",
            stock=5,
        )
        self.url = reverse("add_product_order")

    def test_price_is_taken_from_catalog_not_from_post(self):
        """A forged price_per_item in the POST must be ignored."""
        self.client.force_login(self.user)
        self.client.post(self.url, {
            "product": self.product.id,
            "quantity": 1,
            "price_per_item": "0.01",
        })

        product_order = ProductOrder.objects.get(product=self.product)
        self.product.refresh_from_db()
        self.assertEqual(product_order.price_per_item, self.product.price)
        self.assertNotEqual(str(product_order.price_per_item), "0.01")

    def test_zero_quantity_is_rejected(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, {
            "product": self.product.id,
            "quantity": 0,
        })

        self.assertEqual(response.status_code, 200)  # re-rendered with errors
        self.assertFalse(Order.objects.filter(user=self.user).exists())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)

    def test_quantity_above_stock_is_rejected(self):
        self.client.force_login(self.user)
        self.client.post(self.url, {
            "product": self.product.id,
            "quantity": 99,
        })

        self.assertFalse(Order.objects.filter(user=self.user).exists())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)

    def test_anonymous_cannot_create_an_order(self):
        response = self.client.post(self.url, {
            "product": self.product.id,
            "quantity": 1,
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Order.objects.count(), 0)

    def test_valid_purchase_still_works(self):
        """The fixes must not break the happy path."""
        self.client.force_login(self.user)
        self.client.post(self.url, {
            "product": self.product.id,
            "quantity": 2,
        })

        order = Order.objects.get(user=self.user)
        self.assertEqual(order.product_orders.count(), 1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)

    def test_unavailable_product_cannot_be_bought(self):
        """The templates only hide the Buy button -- the server must enforce it."""
        self.product.available = False
        self.product.save()
        self.client.force_login(self.user)

        self.client.post(self.url, {
            "product": self.product.id,
            "quantity": 1,
        })

        self.assertFalse(Order.objects.filter(user=self.user).exists())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)

    def test_user_without_email_cannot_order(self):
        """No order may carry a placeholder address that looks contactable."""
        emailless = User.objects.create_user(gender='MALE', date_of_birth=ADULT_DOB, 
            username="noemail", password="testpassword", email="",
        )
        self.client.force_login(emailless)

        self.client.post(self.url, {
            "product": self.product.id,
            "quantity": 1,
        })

        self.assertFalse(Order.objects.filter(user=emailless).exists())
        self.assertFalse(
            Order.objects.filter(customer_email="noemail@example.com").exists()
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)

    def test_order_records_the_real_account_email(self):
        self.client.force_login(self.user)
        self.client.post(self.url, {
            "product": self.product.id,
            "quantity": 1,
        })

        order = Order.objects.get(user=self.user)
        self.assertEqual(order.customer_email, self.user.email)

    def test_catalog_row_is_locked_during_checkout(self):
        """Proves select_for_update is actually issued, without spawning threads."""
        self.client.force_login(self.user)

        with CaptureQueriesContext(connection) as queries:
            self.client.post(self.url, {
                "product": self.product.id,
                "quantity": 1,
            })

        self.assertTrue(
            any("FOR UPDATE" in q["sql"].upper() for q in queries),
            "checkout did not lock the product row",
        )

    def test_failure_mid_checkout_rolls_everything_back(self):
        """An orphaned Order must not survive a failure after it was created."""
        self.client.force_login(self.user)

        with patch(
            "orders.services.ProductOrder.objects.create",
            side_effect=RuntimeError("boom"),
        ):
            with self.assertRaises(RuntimeError):
                self.client.post(self.url, {
                    "product": self.product.id,
                    "quantity": 1,
                })

        self.assertEqual(Order.objects.count(), 0)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)
    

class OrderDeleteAPITestCase(TestCase):
    """DELETE /api/orders/<pk>/ -- the customer regrets the purchase.

    Soft delete (is_active=False) plus a stock restore that mirrors the
    checkout decrement.
    """

    def setUp(self):
        self.owner = User.objects.create_user(gender='MALE', date_of_birth=ADULT_DOB, 
            username="regretful", password="testpassword", email="r@example.com")
        self.other = User.objects.create_user(gender='MALE', date_of_birth=ADULT_DOB, 
            username="bystander", password="testpassword", email="b@example.com")
        self.product = Product.objects.create(
            name="Regret Roast", description="d", price="4.00", stock=10)
        self.url = reverse("add_product_order")

    def _buy(self, user, quantity=3):
        self.client.force_login(user)
        self.client.post(self.url, {"product": self.product.id, "quantity": quantity})
        return Order.objects.get(user=user)

    def test_owner_delete_soft_deletes_and_restores_stock(self):
        order = self._buy(self.owner, quantity=3)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 7)  # decremented by the purchase

        response = self.client.delete(reverse("api_order_delete", args=[order.pk]))

        self.assertEqual(response.status_code, 204)
        order.refresh_from_db()
        self.assertFalse(order.is_active)
        self.assertTrue(Order.objects.filter(pk=order.pk).exists())  # row kept
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)  # units returned

    def test_another_users_order_is_not_reachable(self):
        """The tenancy boundary: scoped to user=request.user, so this is a 404."""
        order = self._buy(self.owner, quantity=2)
        self.client.force_login(self.other)

        response = self.client.delete(reverse("api_order_delete", args=[order.pk]))

        self.assertEqual(response.status_code, 404)
        order.refresh_from_db()
        self.assertTrue(order.is_active)

    def test_anonymous_cannot_delete(self):
        order = self._buy(self.owner, quantity=1)
        self.client.logout()

        response = self.client.delete(reverse("api_order_delete", args=[order.pk]))

        self.assertEqual(response.status_code, 403)
        order.refresh_from_db()
        self.assertTrue(order.is_active)

    def test_deleting_twice_does_not_restore_stock_twice(self):
        order = self._buy(self.owner, quantity=4)

        first = self.client.delete(reverse("api_order_delete", args=[order.pk]))
        second = self.client.delete(reverse("api_order_delete", args=[order.pk]))

        self.assertEqual(first.status_code, 204)
        self.assertEqual(second.status_code, 404)  # is_active=True is in the lookup
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)   # not 14

    def test_deleted_order_disappears_from_my_orders(self):
        order = self._buy(self.owner, quantity=1)
        # Flush the "order created" flash message first -- it echoes the order
        # number and would otherwise be mistaken for the order still listing.
        self.client.get(reverse("order_list"))

        self.client.delete(reverse("api_order_delete", args=[order.pk]))

        response = self.client.get(reverse("order_list"))
        self.assertNotContains(response, order.order_number)
        self.assertContains(response, "No orders yet")

    def test_deleted_order_detail_is_no_longer_reachable(self):
        """OrderDetail filters is_active=True, so a soft-deleted order 404s."""
        order = self._buy(self.owner, quantity=1)
        self.client.delete(reverse("api_order_delete", args=[order.pk]))

        response = self.client.get(reverse("order_details", args=[order.pk]))
        self.assertEqual(response.status_code, 404)


@override_settings(ALCOHOL_SERVICE_START_HOUR=0)
class AlcoholAgeGateTestCase(TestCase):
    """The gate lives in place_order, so both the web checkout and Basil's
    create_order tool hit it. Each path is tested separately.

    The bar is forced open (hour 0) so these assert the age gate alone --
    otherwise they'd pass or fail on the wall clock."""

    def setUp(self):
        self.wine = make_product(
            "Alcohol", "Non-Coffee",
            name="Cabernet Test", description="d", price=18.00, stock=5,
        )
        self.shake = make_product(
            "Non-Coffee",
            name="Vanilla Milkshake Test", description="d", price=4.50, stock=5,
        )
        self.adult = make_user(username="adult_buyer", date_of_birth=adult_dob())
        self.minor = make_minor(username="minor_buyer")

    # --- the service, shared by both callers ---

    def test_minor_is_refused_alcohol(self):
        with self.assertRaises(OrderError) as ctx:
            place_order(user=self.minor, product_id=self.wine.pk, quantity=1)
        self.assertIn("under 18", str(ctx.exception))

    def test_refusal_does_not_touch_stock_or_create_an_order(self):
        with self.assertRaises(OrderError):
            place_order(user=self.minor, product_id=self.wine.pk, quantity=1)
        self.wine.refresh_from_db()
        self.assertEqual(self.wine.stock, 5)
        self.assertEqual(Order.objects.count(), 0)

    def test_adult_may_buy_alcohol(self):
        order = place_order(user=self.adult, product_id=self.wine.pk, quantity=1)
        self.assertEqual(order.product_orders.first().product, self.wine)
        self.wine.refresh_from_db()
        self.assertEqual(self.wine.stock, 4)

    def test_the_gate_does_not_over_fire(self):
        """A minor buying a milkshake must still succeed."""
        order = place_order(user=self.minor, product_id=self.shake.pk, quantity=1)
        self.assertEqual(order.product_orders.first().product, self.shake)

    # --- the web checkout ---

    def test_web_checkout_refuses_a_minor(self):
        self.client.force_login(self.minor)
        response = self.client.post(reverse("add_product_order"), {
            "product": self.wine.pk, "quantity": 1,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Order.objects.count(), 0)
        self.wine.refresh_from_db()
        self.assertEqual(self.wine.stock, 5)

    def test_web_checkout_allows_an_adult(self):
        self.client.force_login(self.adult)
        response = self.client.post(reverse("add_product_order"), {
            "product": self.wine.pk, "quantity": 1,
        })
        self.assertRedirects(response, reverse("order_list"))
        self.assertEqual(Order.objects.count(), 1)

    # --- Basil's tool ---

    def test_create_order_tool_refuses_a_minor(self):
        result = create_order(user=self.minor, product_id=self.wine.pk, quantity=1)
        self.assertIn("error", result)
        self.assertIn("under 18", result["error"])
        self.assertEqual(Order.objects.count(), 0)

    def test_create_order_tool_allows_an_adult(self):
        result = create_order(user=self.adult, product_id=self.wine.pk, quantity=1)
        self.assertNotIn("error", result)
        self.assertEqual(Order.objects.count(), 1)

    def test_anonymous_cannot_reach_the_gate_with_no_dob(self):
        result = create_order(user=AnonymousUser(), product_id=self.wine.pk, quantity=1)
        self.assertIn("error", result)
        self.assertEqual(Order.objects.count(), 0)

    def test_is_age_restricted_matches_on_category(self):
        self.assertTrue(is_age_restricted(self.wine))
        self.assertFalse(is_age_restricted(self.shake))
