from django.http import JsonResponse
from .models import AnonAttributes
from django.http import FileResponse

# Endpoint to retrieve an attribute by ID
def get_by_id(request, id):
    if request.method == 'GET':
        attribute = AnonAttributes.objects.get(id=id)
        try:
            return FileResponse(attribute.file.open('rb'), as_attachment=True, filename=attribute.file.name)
        except FileNotFoundError:
            return JsonResponse({'error': 'File not found'}, status=404)
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=400)