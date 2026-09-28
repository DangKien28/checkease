# ==============================================================================
# TÁC GIẢ: Đặng Trung Kiên
# CHI TIẾT: File này được Đặng Trung Kiên tạo mới để đăng ký các endpoint của 
# Gate Engine (tổng hợp điểm & xuất PDF) vào router tổng của dự án Checkease.
# ==============================================================================
from django.urls import path
from . import views

urlpatterns = [
    path('evaluate/', views.evaluate_gate, name='gate-evaluate'),
    path('export-pdf/', views.export_gate_pdf, name='gate-export-pdf'),
]
