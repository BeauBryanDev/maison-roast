from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import Category, Product
from .test_utils import make_product
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
        self.available = make_product(
            "Latte", name="Featured Latte", description="d", price=3.50, stock=5,
        )
        self.hidden = make_product(
            "Latte", name="Discontinued Brew", description="d", price=9.99,
            stock=5, available=False,
        )

    def test_home_lists_only_available_featured_products(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Featured Latte")
        # The strip links straight to Buy Now, so it must not offer the unbuyable.
        self.assertNotContains(response, "Discontinued Brew")

    def test_category_tiles_come_from_the_catalog(self):
        response = self.client.get(reverse("home"))
        names = [c.name for c in response.context["categories"]]
        self.assertIn("Latte", names)


class ProductListFilterTestCase(TestCase):
    def setUp(self):
        make_product("Hot Coffee", name="Hot One", description="d", price=1, stock=1)
        make_product("Cold Coffee", name="Cold One", description="d", price=1, stock=1)

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
            make_product("Hot Coffee", name=f"Hot {i}", description="d",
                         price=1, stock=1)

        response = self.client.get(reverse("product_list"), {"category": "Hot Coffee"})
        self.assertTrue(response.context["is_paginated"])
        # Django's urlencode filter emits %20 for the space, not +. Both are
        # valid; what matters is that the category rides along.
        self.assertContains(response, "page=2&amp;category=Hot%20Coffee")

    def test_second_page_still_filtered(self):
        for i in range(12):
            make_product("Hot Coffee", name=f"Hot {i}", description="d",
                         price=1, stock=1)

        response = self.client.get(reverse("product_list"),
                                   {"category": "Hot Coffee", "page": 2})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Cold One")


class ProductSlugTestCase(TestCase):
    def test_duplicate_names_get_distinct_slugs(self):
        """Two products sharing a name must not collide on the unique slug."""
        first = Product.objects.create(
            name="Duplicate Name", description="d", price=1.00, stock=1
        )
        second = Product.objects.create(
            name="Duplicate Name", description="d", price=1.00, stock=1
        )

        self.assertEqual(first.slug, "duplicate-name")
        self.assertEqual(second.slug, "duplicate-name-2")

    def test_name_without_sluggable_characters(self):
        product = Product.objects.create(
            name="!!!", description="d", price=1.00, stock=1
        )
        self.assertEqual(product.slug, "product")


class ProductAPISecurityTestCase(TestCase):
    """The catalog API is public to read and staff-only to write."""

    def setUp(self):
        self.product = make_product(
            "Hot Coffee",
            name="API Test Product",
            description="Test Description",
            price=10.00,
            stock=10,
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

class ErrorPageTestCase(TestCase):
    """Error templates only render when DEBUG is False, which is why they are
    easy to ship broken -- nobody sees them in development."""

    def test_404_uses_the_vintage_page(self):
        with self.settings(DEBUG=False):
            response = self.client.get("/no-such-page/")

        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")
        self.assertContains(response, "This page has left", status_code=404)
        # It extends base.html, so the nav and the rail come with it.
        self.assertContains(response, "basil-rail", status_code=404)

    def test_404_offers_a_way_out(self):
        with self.settings(DEBUG=False):
            response = self.client.get("/no-such-page/")

        self.assertContains(response, reverse("product_list"), status_code=404)
        self.assertContains(response, reverse("about"), status_code=404)

    def test_403_is_shown_to_a_signed_in_non_staff_user(self):
        """ProductFormView raises PermissionDenied for a customer. Anonymous
        visitors are redirected to login instead and never see this page."""
        customer = User.objects.create_user(
            username="nosy", password="testpassword", email="nosy@example.com")
        self.client.force_login(customer)

        with self.settings(DEBUG=False):
            response = self.client.get(reverse("product_add"))

        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, "403.html")
        self.assertContains(response, "Staff only", status_code=403)
        self.assertContains(response, "nosy", status_code=403)

    def test_500_renders_with_no_context_at_all(self):
        """Django renders 500.html with an empty context -- no request, no user,
        no context processors. Extending base.html would raise here."""
        from django.template.loader import render_to_string

        html = render_to_string("500.html")

        self.assertIn("Something boiled over", html)
        self.assertIn("#1a1108", html)  # styling is inline, not from main.css

    def test_500_does_not_depend_on_the_site_shell(self):
        """Checked on the rendered output, not the source -- the source
        mentions csrf_token in a comment explaining why it cannot use one."""
        from django.template.loader import get_template, render_to_string

        self.assertNotIn("{% extends", get_template("500.html").template.source)

        html = render_to_string("500.html")
        self.assertNotIn("csrf", html)
        self.assertNotIn("/static/", html)
        self.assertNotIn("basil-rail", html)


class FavouritesPageTestCase(TestCase):
    """Favourites are localStorage-only, so the server side is a shell plus a
    heart button on every card. What is asserted here is the contract the JS
    relies on -- the ids, the markers and the public read it fetches."""

    def setUp(self):
        self.product = make_product(
            'Coffee',
            name='Vanilla Latte', description='Sweet and milky',
            price='3.80', stock=10)

    def test_favourites_page_is_public(self):
        response = self.client.get(reverse('favourites'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'products/favourites.html')

    def test_favourites_page_renders_no_products_server_side(self):
        # The grid is filled by favourites.js. If the product name appears in
        # the HTML, someone has started rendering favourites from the database.
        response = self.client.get(reverse('favourites'))
        self.assertNotContains(response, 'Vanilla Latte')
        self.assertContains(response, 'id="favourites-grid"')

    def test_menu_card_carries_a_favourite_button_with_the_product_id(self):
        response = self.client.get(reverse('product_list'))
        self.assertContains(response, f'data-favourite="{self.product.id}"')
        self.assertContains(response, 'heart_icon.svg')

    def test_favourites_is_in_the_nav_for_anonymous_visitors(self):
        # Per-browser storage, so there is nothing to log in for.
        response = self.client.get(reverse('home'))
        self.assertContains(response, reverse('favourites'))

    def test_catalog_api_read_is_public(self):
        # favourites.js fetches this anonymously; a permission change that
        # locked reads would empty the page with no other symptom.
        response = self.client.get(reverse('product_list_api'))
        self.assertEqual(response.status_code, 200)


class BarPageTestCase(TestCase):
    """The bar page is the Alcohol category and nothing else."""

    def setUp(self):
        self.wine = make_product(
            'Alcohol', name='Red Wine', description='Deep and dry',
            price='7.50', stock=15)
        self.coffee = make_product(
            'Coffee', name='Espresso', description='Short and strong',
            price='2.99', stock=50)

    def test_bar_page_is_public(self):
        response = self.client.get(reverse('bar'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'products/bar.html')

    def test_bar_shows_only_alcohol(self):
        response = self.client.get(reverse('bar'))
        self.assertContains(response, 'Red Wine')
        self.assertNotContains(response, 'Short and strong')

    def test_bar_carries_the_house_notice(self):
        response = self.client.get(reverse('bar'))
        self.assertContains(response, 'the clock strikes 18:00')
        self.assertContains(response, 'Reggae Singer')

    def test_a_product_in_two_categories_is_listed_once(self):
        # Alcohol overlaps Non-Coffee on the real catalog; the join must not
        # duplicate the card.
        both = make_product(
            'Alcohol', 'Non-Coffee', name='Cabernet Sauvignon',
            description='House red', price='6.00', stock=20)
        response = self.client.get(reverse('bar'))
        self.assertEqual(response.content.decode().count(
            f'data-favourite="{both.id}"'), 1)

    def test_bar_cards_carry_the_favourite_button(self):
        response = self.client.get(reverse('bar'))
        self.assertContains(response, f'data-favourite="{self.wine.id}"')

    def test_bar_carries_the_wallpaper_band(self):
        response = self.client.get(reverse('bar'))
        self.assertContains(response, 'bar_wallpaper.jpg')
        self.assertContains(response, 'Come, Drink and Cheers with us!')

    def test_bar_is_in_the_nav(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, reverse('bar'))
