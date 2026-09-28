import json
from decimal import Decimal
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from apps.core.models import SystemSetting

def landing_view(request):
    return render(request, 'pages/landing.html')

def settings_view(request):
    keys = ['api_key_openai', 'api_key_gemini', 'api_key_claude', 'application_tier_config', 'default_weights']
    settings_dict = {}
    for setting in SystemSetting.objects.filter(key__in=keys):
        settings_dict[setting.key] = setting.value
        
    context = {
        'api_key_openai': settings_dict.get('api_key_openai', ''),
        'api_key_gemini': settings_dict.get('api_key_gemini', ''),
        'api_key_claude': settings_dict.get('api_key_claude', ''),
    }
    return render(request, 'pages/settings.html', context)

@csrf_exempt
@require_POST
def update_global_settings(request):
    try:
        data = json.loads(request.body)
        
        # 1. Lưu API Key của các LLM (OpenAI, Gemini, Claude)
        llm_keys = data.get('llm_keys', {})
        for provider, key in llm_keys.items():
            if provider in ['openai', 'gemini', 'claude']:
                setting, _ = SystemSetting.objects.get_or_create(key=f"api_key_{provider}")
                setting.value = key
                setting.save()

        # 2. Lưu cấu hình Application Tier (Tier 1, 2, 3)
        tier_config = data.get('tier_config')
        if tier_config:
            setting, _ = SystemSetting.objects.get_or_create(key="application_tier_config")
            setting.value = json.dumps(tier_config)
            setting.save()

        # 3. Validation CỰC KỲ QUAN TRỌNG: W1 + W2 == 1.0
        # (Người dùng có thể truyền w1_testing, w2_source_code ở global default hoặc cho 1 cấu hình cụ thể)
        if 'w1_testing' in data and 'w2_source_code' in data:
            try:
                w1 = Decimal(str(data['w1_testing']))
                w2 = Decimal(str(data['w2_source_code']))
            except Exception:
                return JsonResponse({"error": "Trọng số không hợp lệ"}, status=400)
                
            if (w1 + w2) != Decimal('1.0'):
                return JsonResponse({"error": "Tổng trọng số W1 (Testing) và W2 (Source Code) phải bằng chính xác 1.0!"}, status=400)
                
            setting, _ = SystemSetting.objects.get_or_create(key="default_weights")
            setting.value = json.dumps({"w1_testing": float(w1), "w2_source_code": float(w2)})
            setting.save()

        return JsonResponse({"message": "Đã lưu cấu hình hệ thống thành công!"}, status=200)

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON data"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
