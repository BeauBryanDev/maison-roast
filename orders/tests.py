from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext

from .views import MYOrderslist
from .models import Order, ProductOrder
from products.models import Product

User = get_user_model()

class OrderTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
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
            product_name=self.product,
            quantity=1,
            price_per_item=10.00,
        )

    def test_order_str(self):
        self.assertEqual(str(self.order), "Order 1234567890 -True by Test Customer")

    def test_product_order_str(self):
        # ProductOrder __str__: f"{self.quantity} x {self.product_name} for Order {self.order.order_number}"
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
        self.user = User.objects.create_user(
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
            product_name=self.product,
            quantity=1,
            price_per_item=10.00,
        )
        self.my_order_view = MYOrderslist.as_view()

    def test_my_order_view(self):
        self.client.login(username="testuser", password="testpassword")
        response = self.client.get(reverse("order_list")) # Assuming order_list is the name for my_order_view
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.order.order_number)


class CheckoutSecurityTestCase(TestCase):
    """Guard the checkout path against tampered POST data.

    Each test here corresponds to a fixed exploit -- if one starts failing, the
    hole it covers has been reopened.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="buyer",
            password="testpassword",
            email="buyer@example.com",
        )
        self.product = Product.objects.create(
            name="Checkout Test Product",
            description="Test Description",
            price="2.99",
            stock=5,
            category="Hot Coffee",
        )
        self.url = reverse("add_product_order")

    def test_price_is_taken_from_catalog_not_from_post(self):
        """A forged price_per_item in the POST must be ignored."""
        self.client.force_login(self.user)
        self.client.post(self.url, {
            "product_name": self.product.id,
            "quantity": 1,
            "price_per_item": "0.01",
        })

        product_order = ProductOrder.objects.get(product_name=self.product)
        self.product.refresh_from_db()
        self.assertEqual(product_order.price_per_item, self.product.price)
        self.assertNotEqual(str(product_order.price_per_item), "0.01")

    def test_zero_quantity_is_rejected(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, {
            "product_name": self.product.id,
            "quantity": 0,
        })

        self.assertEqual(response.status_code, 200)  # re-rendered with errors
        self.assertFalse(Order.objects.filter(user=self.user).exists())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)

    def test_quantity_above_stock_is_rejected(self):
        self.client.force_login(self.user)
        self.client.post(self.url, {
            "product_name": self.product.id,
            "quantity": 99,
        })

        self.assertFalse(Order.objects.filter(user=self.user).exists())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)

    def test_anonymous_cannot_create_an_order(self):
        response = self.client.post(self.url, {
            "product_name": self.product.id,
            "quantity": 1,
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Order.objects.count(), 0)

    def test_valid_purchase_still_works(self):
        """The fixes must not break the happy path."""
        self.client.force_login(self.user)
        self.client.post(self.url, {
            "product_name": self.product.id,
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
            "product_name": self.product.id,
            "quantity": 1,
        })

        self.assertFalse(Order.objects.filter(user=self.user).exists())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)

    def test_user_without_email_cannot_order(self):
        """No order may carry a placeholder address that looks contactable."""
        emailless = User.objects.create_user(
            username="noemail", password="testpassword", email="",
        )
        self.client.force_login(emailless)

        self.client.post(self.url, {
            "product_name": self.product.id,
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
            "product_name": self.product.id,
            "quantity": 1,
        })

        order = Order.objects.get(user=self.user)
        self.assertEqual(order.customer_email, self.user.email)

    def test_catalog_row_is_locked_during_checkout(self):
        """Proves select_for_update is actually issued, without spawning threads."""
        self.client.force_login(self.user)

        with CaptureQueriesContext(connection) as queries:
            self.client.post(self.url, {
                "product_name": self.product.id,
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
            "orders.views.ProductOrder.objects.create",
            side_effect=RuntimeError("boom"),
        ):
            with self.assertRaises(RuntimeError):
                self.client.post(self.url, {
                    "product_name": self.product.id,
                    "quantity": 1,
                })

        self.assertEqual(Order.objects.count(), 0)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)
    