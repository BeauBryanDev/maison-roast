from datetime import date, timedelta
from unittest.mock import patch

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from .forms import CustomUserCreationForm

from products.models import Product
from orders.models import Order, ProductOrder
from users.test_utils import ADULT_DOB, adult_dob, make_minor, make_user
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
        self.user = User.objects.create_user(gender='MALE', date_of_birth=ADULT_DOB, **self.user_data)

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
            'address': '123 Test St',
            'gender': 'FEMALE',
            'date_of_birth': '1995-04-17',
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
        self.superuser = User.objects.create_superuser(gender='MALE', date_of_birth=ADULT_DOB, 
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
        for field in ("email", "phone_number", "address", "gender", "date_of_birth"):
            with self.subTest(field=field):
                self.assertContains(response, f'name="{field}"')

    def test_two_users_can_be_added_through_the_admin(self):
        for i in (1, 2):
            response = self.client.post("/admin/users/customuser/add/", {
                "username": f"staffer{i}",
                "email": f"staffer{i}@example.com",
                "password1": "Sup3r-Secret-Pw!",
                "password2": "Sup3r-Secret-Pw!",
                "gender": "MALE",
                "date_of_birth": "1990-01-01",
            })
            self.assertIn(response.status_code, (200, 302))

        self.assertTrue(User.objects.filter(username="staffer1").exists())
        self.assertTrue(User.objects.filter(username="staffer2").exists())

    def test_order_change_form_shows_line_items_inline(self):
        product = Product.objects.create(
            name="Inline Test Product", description="d", price=3.00, stock=5,
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


class ProfileAPITestCase(TestCase):
    """/api/users/me/ -- the account as its owner sees it.

    Tenancy is enforced by get_object() returning request.user; there is no id
    in the URL, so these tests assert one account can never reach another.
    """

    def setUp(self):
        self.user = User.objects.create_user(gender='MALE', date_of_birth=ADULT_DOB, 
            username="owner", password="Orig-Passw0rd!", email="owner@example.com",
            first_name="Ada", last_name="Lovelace",
            phone_number="0100", address="1 Old Street",
        )
        self.other = User.objects.create_user(gender='MALE', date_of_birth=ADULT_DOB, 
            username="intruder", password="Other-Passw0rd!", email="other@example.com",
            first_name="Someone", last_name="Else",
        )
        self.url = reverse("api_me")
        self.password_url = reverse("api_me_password")

    # ---------------------------------------------------------- permissions --
    def test_anonymous_is_refused_every_method(self):
        for method in ("get", "put", "patch", "delete"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(
                    self.url, data={}, content_type="application/json")
                self.assertEqual(response.status_code, 403)

    def test_get_returns_only_the_logged_in_account(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["username"], "owner")
        self.assertNotEqual(response.json()["username"], "intruder")

    # ---------------------------------------------------------------- update --
    def test_put_updates_every_editable_field(self):
        self.client.force_login(self.user)
        response = self.client.put(self.url, data={
            "first_name": "Grace", "last_name": "Hopper",
            "phone_number": "0200", "address": "2 New Street",
        }, content_type="application/json")

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Grace")
        self.assertEqual(self.user.address, "2 New Street")

    def test_patch_updates_one_field_and_leaves_the_rest(self):
        self.client.force_login(self.user)
        response = self.client.patch(self.url, data={"phone_number": "0300"},
                                     content_type="application/json")

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone_number, "0300")
        self.assertEqual(self.user.first_name, "Ada")   # untouched

    def test_username_and_email_cannot_be_changed(self):
        """They are read_only on the serializer, so a forged body is ignored."""
        self.client.force_login(self.user)
        response = self.client.put(self.url, data={
            "username": "admin", "email": "hacker@example.com",
            "first_name": "Ada", "last_name": "Lovelace",
            "phone_number": "0100", "address": "1 Old Street",
        }, content_type="application/json")

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "owner")
        self.assertEqual(self.user.email, "owner@example.com")
 
    def test_password_change_requires_the_current_password(self):
        self.client.force_login(self.user)
        response = self.client.post(self.password_url, data={
            "old_password": "wrong-password",
            "new_password1": "Brand-New-Pw1!", "new_password2": "Brand-New-Pw1!",
        }, content_type="application/json")

        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Orig-Passw0rd!"))

    def test_password_change_keeps_the_session_alive(self):
        """Without update_session_auth_hash the user is logged out of their own
        session the instant they change their password."""
        self.client.force_login(self.user)
        response = self.client.post(self.password_url, data={
            "old_password": "Orig-Passw0rd!",
            "new_password1": "Brand-New-Pw1!", "new_password2": "Brand-New-Pw1!",
        }, content_type="application/json")

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Brand-New-Pw1!"))
        # still authenticated on the same session
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_mismatched_new_passwords_are_rejected(self):
        self.client.force_login(self.user)
        response = self.client.post(self.password_url, data={
            "old_password": "Orig-Passw0rd!",
            "new_password1": "Brand-New-Pw1!", "new_password2": "Different-Pw1!",
        }, content_type="application/json")

        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Orig-Passw0rd!"))

 
    def test_delete_without_password_is_refused(self):
        self.client.force_login(self.user)
        response = self.client.delete(self.url, data={},
                                      content_type="application/json")

        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_delete_with_wrong_password_is_refused(self):
        self.client.force_login(self.user)
        response = self.client.delete(self.url, data={"password": "nope"},
                                      content_type="application/json")

        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_delete_deactivates_keeps_the_row_and_blocks_login(self):
        self.client.force_login(self.user)
        response = self.client.delete(self.url, data={"password": "Orig-Passw0rd!"},
                                      content_type="application/json")

        self.assertEqual(response.status_code, 204)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())  # soft delete
        self.assertFalse(
            self.client.login(username="owner", password="Orig-Passw0rd!"))


class ProfilePageTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(gender='MALE', date_of_birth=ADULT_DOB, 
            username="pageuser", password="testpassword", email="page@example.com")
        self.url = reverse("profile")

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/users/login/", response.url)

    def test_profile_page_renders_for_its_owner(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/profile.html")
        self.assertContains(response, "pageuser")
        # CSRF token must be present or every fetch() 403s
        self.assertContains(response, "csrfmiddlewaretoken")


class AgeComputationTestCase(TestCase):
    """CustomUser.age -- the basis of the alcohol gate."""

    def _user_born(self, dob, username="ageuser"):
        return make_user(username=username, date_of_birth=dob)

    def test_age_the_day_before_a_birthday(self):
        today = date(2026, 9, 3)
        user = self._user_born(date(2008, 9, 4))
        with patch("users.models.date") as mock_date:
            mock_date.today.return_value = today
            self.assertEqual(user.age, 17)

    def test_age_on_the_birthday(self):
        today = date(2026, 9, 3)
        user = self._user_born(date(2008, 9, 3))
        with patch("users.models.date") as mock_date:
            mock_date.today.return_value = today
            self.assertEqual(user.age, 18)

    def test_age_the_day_after_a_birthday(self):
        today = date(2026, 9, 3)
        user = self._user_born(date(2008, 9, 2))
        with patch("users.models.date") as mock_date:
            mock_date.today.return_value = today
            self.assertEqual(user.age, 18)

    def test_leap_day_birthday(self):
        user = self._user_born(date(2008, 2, 29))
        with patch("users.models.date") as mock_date:
            mock_date.today.return_value = date(2026, 2, 28)
            self.assertEqual(user.age, 17)
            mock_date.today.return_value = date(2026, 3, 1)
            self.assertEqual(user.age, 18)

    def test_is_of_legal_age(self):
        self.assertTrue(make_user(username="adult", date_of_birth=adult_dob()).is_of_legal_age())
        self.assertFalse(make_minor().is_of_legal_age())

    def test_cutoff_finds_minors_in_sql(self):
        """legal_age_cutoff drives a date_of_birth query, no computed column."""
        make_user(username="grown", date_of_birth=adult_dob())
        minor = make_minor()
        found = User.objects.filter(date_of_birth__gt=User.legal_age_cutoff())
        self.assertEqual([u.pk for u in found], [minor.pk])


class MandatorySignupFieldsTestCase(TestCase):
    """gender and date_of_birth are required at registration."""

    def setUp(self):
        self.url = reverse("register")
        self.payload = {
            "username": "signup",
            "email": "signup@example.com",
            "password1": "newpassword123",
            "password2": "newpassword123",
            "gender": "FEMALE",
            "date_of_birth": "1995-04-17",
        }

    def test_valid_signup_stores_both(self):
        response = self.client.post(self.url, self.payload)
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username="signup")
        self.assertEqual(user.gender, "FEMALE")
        self.assertEqual(user.date_of_birth, date(1995, 4, 17))

    def test_missing_gender_is_rejected(self):
        self.payload.pop("gender")
        response = self.client.post(self.url, self.payload)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="signup").exists())

    def test_missing_date_of_birth_is_rejected(self):
        self.payload.pop("date_of_birth")
        response = self.client.post(self.url, self.payload)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="signup").exists())

    def test_future_date_of_birth_is_rejected(self):
        self.payload["date_of_birth"] = (date.today() + timedelta(days=1)).isoformat()
        response = self.client.post(self.url, self.payload)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="signup").exists())

    def test_absurd_date_of_birth_is_rejected(self):
        self.payload["date_of_birth"] = "1820-01-01"
        response = self.client.post(self.url, self.payload)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="signup").exists())

    def test_invalid_gender_choice_is_rejected(self):
        self.payload["gender"] = "ROBOT"
        response = self.client.post(self.url, self.payload)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="signup").exists())

    def test_register_page_renders_both_inputs(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'name="gender"')
        self.assertContains(response, 'type="date"')


class ProfileImmutableFieldsTestCase(TestCase):
    """gender and date_of_birth are read-only, like username and email."""

    def setUp(self):
        self.user = make_user(username="immutable", date_of_birth=date(1990, 1, 1))
        self.client.force_login(self.user)
        self.url = "/api/users/me/"

    def test_get_exposes_them(self):
        body = self.client.get(self.url).json()
        self.assertEqual(body["gender"], "MALE")
        self.assertEqual(body["date_of_birth"], "1990-01-01")
        self.assertEqual(body["age"], self.user.age)

    def test_patch_is_ignored(self):
        response = self.client.patch(
            self.url,
            {"gender": "FEMALE", "date_of_birth": "2020-01-01"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.gender, "MALE")
        self.assertEqual(self.user.date_of_birth, date(1990, 1, 1))

    def test_put_is_ignored(self):
        response = self.client.put(
            self.url,
            {"first_name": "Ok", "gender": "OTHER", "date_of_birth": "2020-01-01"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Ok")
        self.assertEqual(self.user.gender, "MALE")
        self.assertEqual(self.user.date_of_birth, date(1990, 1, 1))

    def test_profile_page_shows_them_without_a_save_button(self):
        response = self.client.get(reverse("profile"))
        self.assertContains(response, "Male")
        self.assertNotContains(response, 'data-patch="date_of_birth"')
        self.assertNotContains(response, 'data-patch="gender"')
