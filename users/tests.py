from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from .forms import CustomUserCreationForm

from products.models import Product
from orders.models import Order, ProductOrder
User = get_user_model()

class UserAuthenticationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.register_url = reverse('register')
        self.login_url = reverse('login')
        self.logout_url = reverse('logout')
        self.home_url = reverse('home')
        
        # Create a test user for login tests
        self.user_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'testpassword123'
        }
        self.user = User.objects.create_user(**self.user_data)

    def test_login_view_status(self):
        """Test that login page is accessible for unauthenticated users"""
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/login.html')

    def test_register_view_status(self):
        """Test that register page is accessible for unauthenticated users"""
        response = self.client.get(self.register_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/register.html')

    def test_logout_view_status(self):
        """Test that logout page (confirmation) is accessible"""
        self.client.force_login(self.user)
        response = self.client.get(self.logout_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/logout.html')

    def test_user_login(self):
        """Test valid login"""
        response = self.client.post(self.login_url, {
            'username': self.user_data['username'],
            'password': self.user_data['password']
        })
        # Should redirect after success (default is home or profile)
        # LoginView default redirect is LOGIN_REDIRECT_URL = 'home' (from settings)
        self.assertRedirects(response, self.home_url)
        # Check if user is authenticated
        self.assertTrue(int(self.client.session['_auth_user_id']) == self.user.pk)

    def test_user_logout(self):
        """Test logout functionality"""
        self.client.login(username=self.user_data['username'], password=self.user_data['password'])
        response = self.client.post(self.logout_url)
        # Should redirect to home
        self.assertRedirects(response, self.home_url)
        # Check session is cleared
        self.assertFalse('_auth_user_id' in self.client.session)

    def test_register_authenticated_redirect(self):
        """Test that authenticated users are redirected away from register page"""
        self.client.force_login(self.user)
        response = self.client.get(self.register_url)
        self.assertRedirects(response, self.home_url)


class UserRegistrationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.register_url = reverse('register')
        self.home_url = reverse('home')

    def test_user_creation_success(self):
        """Test successful user registration"""
        payload = {
            'username': 'newuser',
            'email': 'new@example.com',
            'password1': 'newpassword123',
            'password2': 'newpassword123',
            'first_name': 'New',
            'last_name': 'User',
            'phone_number': '1234567890',
            'address': '123 Test St'
        }
        response = self.client.post(self.register_url, payload)
        
        # Check redirection to home
        self.assertRedirects(response, self.home_url)
        
        # Check user created
        self.assertTrue(User.objects.filter(username='newuser').exists())
        new_user = User.objects.get(username='newuser')
        self.assertEqual(new_user.email, 'new@example.com')
        self.assertEqual(new_user.first_name, 'New')
        
        # Check user is logged in
        self.assertTrue(int(self.client.session['_auth_user_id']) == new_user.pk)

    def test_user_creation_password_mismatch(self):
        """Test registration failure with mismatched passwords"""
        payload = {
            'username': 'baduser',
            'email': 'bad@example.com',
            'password1': 'password123',
            'password2': 'mismatch123',
        }
        response = self.client.post(self.register_url, payload)
        
        # Should not redirect, should re-render form
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='baduser').exists())
        
        # Manually check form errors
        form = response.context['form']
        self.assertTrue(form.errors)
        self.assertIn('password2', form.errors)
        self.assertEqual(form.errors['password2'], ["The two password fields didn’t match."])


class AdminSmokeTestCase(TestCase):
    """The admin is the staff-facing half of this app and had no tests at all.

    These exercise every registered screen so a bad ModelAdmin option (which
    Django only raises at request time, not at `check` time) cannot ship silently.
    """

    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="root", password="testpassword", email="root@example.com",
        )
        self.client.force_login(self.superuser)

    def test_all_admin_changelists_render(self):
        for url in (
            "/admin/users/customuser/",
            "/admin/products/product/",
            "/admin/orders/order/",
            "/admin/orders/productorder/",
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_all_admin_add_forms_render(self):
        for url in (
            "/admin/users/customuser/add/",
            "/admin/products/product/add/",
            "/admin/orders/order/add/",
            "/admin/orders/productorder/add/",
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_add_user_form_collects_email(self):
        """email is unique and non-blank; without it on the add form the second
        user created through the admin fails with an IntegrityError."""
        response = self.client.get("/admin/users/customuser/add/")
        for field in ("email", "phone_number", "address"):
            with self.subTest(field=field):
                self.assertContains(response, f'name="{field}"')

    def test_two_users_can_be_added_through_the_admin(self):
        for i in (1, 2):
            response = self.client.post("/admin/users/customuser/add/", {
                "username": f"staffer{i}",
                "email": f"staffer{i}@example.com",
                "password1": "Sup3r-Secret-Pw!",
                "password2": "Sup3r-Secret-Pw!",
            })
            self.assertIn(response.status_code, (200, 302))

        self.assertTrue(User.objects.filter(username="staffer1").exists())
        self.assertTrue(User.objects.filter(username="staffer2").exists())

    def test_order_change_form_shows_line_items_inline(self):
        product = Product.objects.create(
            name="Inline Test Product", description="d", price=3.00, stock=5, category="c",
        )
        order = Order.objects.create(
            user=self.superuser, order_number="ADM-1", customer_name="Root",
            customer_email="root@example.com", is_active=True,
        )
        ProductOrder.objects.create(
            order=order, product=product, quantity=2, price_per_item=product.price,
        )

        response = self.client.get(f"/admin/orders/order/{order.pk}/change/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "product_orders-0-quantity")
