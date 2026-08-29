from django.shortcuts import render, redirect
from django.contrib.auth import logout, login
from django.views import View
from django.contrib import messages
from .forms import CustomUserCreationForm

# Create your views here.

class LogoutView(View):
    """Handle logout with confirmation page"""

    def get(self, request):
        """Show logout confirmation page"""
        return render(request, 'users/logout.html')

    def post(self, request):
        """Actually logout the user"""
        logout(request)
        
        return redirect('home')


class RegisterView(View):
    """Handle user registration"""

    def get(self, request):
        """Show registration form"""
        if request.user.is_authenticated:
            return redirect('home')
        
        form = CustomUserCreationForm()
        
        return render(request, 'users/register.html', {'form': form})

    def post(self, request):
        """Process registration form"""
        form = CustomUserCreationForm(request.POST)
        
        if form.is_valid():
            
            user = form.save()
            
            # Automatically login the user after registration
            login(request, user)
            
            messages.success(request, 
                             f'Welcome to Coffee Shop, {user.username}! Your account has been created successfully.')
            
            return redirect('home')
        
        return render(request, 'users/register.html', {'form': form})
