from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import Product
from django.urls import reverse

User = get_user_model()

# Create your tests here.

class ProductTestCase(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name="Test Product",
            description="Test Description",
            price=10.00,
            stock=10,
            product_image="https://example.com/test.jpg",
        )   
        
    def test_product_str(self):
 
        self.assertEqual(str(self.product), "Test Product - $10.00 - Stock: 10")


class ProductListViewTestCase(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name="Test Product",
            description="Test Description",
            price=10.00,
            stock=10,
            product_image="https://example.com/test.jpg",
        )   
        
    def test_product_list_view(self):
        response = self.client.get(reverse("product_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.name)

    
    def test_product_detail_view(self):
        response = self.client.get(reverse("product_detail", args=[self.product.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.name)


class ProductSlugTestCase(TestCase):
    def test_duplicate_names_get_distinct_slugs(self):
        """Two products sharing a name must not collide on the unique slug."""
        first = Product.objects.create(
            name="Duplicate Name", description="d", price=1.00, stock=1, category="c",
        )
        second = Product.objects.create(
            name="Duplicate Name", description="d", price=1.00, stock=1, category="c",
        )

        self.assertEqual(first.slug, "duplicate-name")
        self.assertEqual(second.slug, "duplicate-name-2")

    def test_name_without_sluggable_characters(self):
        product = Product.objects.create(
            name="!!!", description="d", price=1.00, stock=1, category="c",
        )
        self.assertEqual(product.slug, "product")


class ProductAPISecurityTestCase(TestCase):
    """The catalog API is public to read and staff-only to write."""

    def setUp(self):
        self.product = Product.objects.create(
            name="API Test Product",
            description="Test Description",
            price=10.00,
            stock=10,
            category="Hot Coffee",
        )
        self.customer = User.objects.create_user(
            username="customer", password="testpassword", email="customer@example.com",
        )
        self.staff = User.objects.create_user(
            username="shopowner", password="testpassword",
            email="owner@example.com", is_staff=True,
        )
        self.list_url = reverse("product_list_api")
        self.payload = {
            "name": "Injected Product",
            "description": "Should not be created",
            "price": "1.00",
            "stock": 1,
            "category": "Hot Coffee",
        }

    def test_anonymous_read_is_allowed(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)

    def test_anonymous_create_is_forbidden(self):
        response = self.client.post(self.list_url, self.payload)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Product.objects.count(), 1)

    def test_anonymous_delete_is_forbidden(self):
        response = self.client.delete(f"{self.list_url}?id={self.product.id}")
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())

    def test_customer_create_is_forbidden(self):
        """Being registered is not enough -- catalog edits are a staff action."""
        self.client.force_login(self.customer)
        response = self.client.post(self.list_url, self.payload)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Product.objects.count(), 1)

    def test_staff_create_is_allowed(self):
        self.client.force_login(self.staff)
        response = self.client.post(self.list_url, self.payload)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Product.objects.count(), 2)

    def test_missing_id_returns_404_not_500(self):
        """Removing the unreachable except must not change the 404 behaviour."""
        response = self.client.get(f"{self.list_url}?id=999999")
        self.assertEqual(response.status_code, 404)


class ProductAddViewPermissionTestCase(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username="customer", password="testpassword", email="customer@example.com",
        )
        self.staff = User.objects.create_user(
            username="shopowner", password="testpassword",
            email="owner@example.com", is_staff=True,
        )
        self.url = reverse("product_add")

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/users/login/", response.url)

    def test_customer_is_forbidden(self):
        self.client.force_login(self.customer)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_staff_can_open_the_form(self):
        self.client.force_login(self.staff)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)    