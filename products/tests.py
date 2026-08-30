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


class AboutViewTestCase(TestCase):
    def test_about_page_renders(self):
        response = self.client.get(reverse("about"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "products/about.html")
        self.assertContains(response, "brewed with passion")

    def test_about_is_public(self):
        """No login wall on the story page."""
        self.assertEqual(self.client.get(reverse("about")).status_code, 200)


class HomeViewTestCase(TestCase):
    def setUp(self):
        self.available = Product.objects.create(
            name="Featured Latte", description="d", price=3.50, stock=5, category="Latte",
        )
        self.hidden = Product.objects.create(
            name="Discontinued Brew", description="d", price=9.99, stock=5,
            category="Latte", available=False,
        )

    def test_home_lists_only_available_featured_products(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Featured Latte")
        # The strip links straight to Buy Now, so it must not offer the unbuyable.
        self.assertNotContains(response, "Discontinued Brew")

    def test_category_tiles_come_from_the_catalog(self):
        response = self.client.get(reverse("home"))
        self.assertIn("Latte", response.context["categories"])


class ProductListFilterTestCase(TestCase):
    def setUp(self):
        Product.objects.create(name="Hot One", description="d", price=1, stock=1,
                               category="Hot Coffee")
        Product.objects.create(name="Cold One", description="d", price=1, stock=1,
                               category="Cold Coffee")

    def test_category_filter_narrows_the_menu(self):
        response = self.client.get(reverse("product_list"), {"category": "Hot Coffee"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Hot One")
        self.assertNotContains(response, "Cold One")

    def test_no_filter_shows_everything(self):
        response = self.client.get(reverse("product_list"))
        self.assertContains(response, "Hot One")
        self.assertContains(response, "Cold One")

    def test_unknown_category_is_not_an_error(self):
        response = self.client.get(reverse("product_list"), {"category": "Nope"})
        self.assertEqual(response.status_code, 200)

    def test_pagination_links_keep_the_category(self):
        """A bare ?page=2 would silently drop the filter and dump the visitor
        back into the full menu."""
        for i in range(12):  # paginate_by = 9, so this spans two pages
            Product.objects.create(name=f"Hot {i}", description="d", price=1,
                                   stock=1, category="Hot Coffee")

        response = self.client.get(reverse("product_list"), {"category": "Hot Coffee"})
        self.assertTrue(response.context["is_paginated"])
        # Django's urlencode filter emits %20 for the space, not +. Both are
        # valid; what matters is that the category rides along.
        self.assertContains(response, "page=2&amp;category=Hot%20Coffee")

    def test_second_page_still_filtered(self):
        for i in range(12):
            Product.objects.create(name=f"Hot {i}", description="d", price=1,
                                   stock=1, category="Hot Coffee")

        response = self.client.get(reverse("product_list"),
                                   {"category": "Hot Coffee", "page": 2})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Cold One")


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

    def test_staff_can_create_a_product(self):
        """The ModelForm conversion must not break the actual save path."""
        self.client.force_login(self.staff)
        response = self.client.post(self.url, {
            "name": "Flat White",
            "description": "Silky and strong",
            "price": "4.50",
            "stock": 12,
            "available": "on",
            "product_image": "https://example.com/flat-white.jpg",
            "category": "Latte",
        })

        self.assertEqual(response.status_code, 302)
        product = Product.objects.get(name="Flat White")
        self.assertEqual(str(product.price), "4.50")
        self.assertEqual(product.stock, 12)
        self.assertTrue(product.available)
        # slug is excluded from the form and generated by Product.save()
        self.assertEqual(product.slug, "flat-white")

    def test_negative_price_is_rejected(self):
        """clean_price must survive the Form -> ModelForm conversion."""
        self.client.force_login(self.staff)
        response = self.client.post(self.url, {
            "name": "Free Coffee",
            "description": "Suspicious",
            "price": "-1.00",
            "stock": 1,
            "category": "Latte",
        })

        self.assertEqual(response.status_code, 200)  # re-rendered, not saved
        self.assertFalse(Product.objects.filter(name="Free Coffee").exists())
        self.assertIn("price", response.context["form"].errors)

    def test_invalid_submission_shows_errors_and_keeps_input(self):
        """The old template rendered no errors at all -- a bad submission came
        back blank with no explanation (Refactor_backend.md #15)."""
        self.client.force_login(self.staff)
        response = self.client.post(self.url, {
            "name": "Free Coffee",
            "description": "Suspicious",
            "price": "-1.00",
            "stock": 7,
            "category": "Latte",
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Price cannot be negative")
        # the staff member's typing must survive the round trip
        self.assertContains(response, 'value="Free Coffee"')
        self.assertContains(response, 'value="7"')

    def test_unchecked_available_saves_as_false(self):
        """The template posts `available` only when the box is ticked."""
        self.client.force_login(self.staff)
        self.client.post(self.url, {
            "name": "Seasonal Blend",
            "description": "Not on sale yet",
            "price": "6.00",
            "stock": 3,
            "category": "Espresso",
        })

        product = Product.objects.get(name="Seasonal Blend")
        self.assertFalse(product.available)    