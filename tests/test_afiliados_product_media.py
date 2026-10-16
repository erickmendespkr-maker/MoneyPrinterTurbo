from app.services.afiliados_product_media import validate_product_paths


def test_reject_unowned_photo():
    owner = '11111111-1111-4111-8111-111111111111'
    source = {'mode': 'images', 'image_paths': ['22222222-2222-4222-8222-222222222222/photo.jpg']}
    try:
        validate_product_paths(source, owner)
    except ValueError:
        return
    raise AssertionError('foreign photo accepted')
