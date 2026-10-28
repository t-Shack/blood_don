from django import template

register = template.Library()

MINUS_SIGN = '−'


@register.filter(is_safe=True)
def rh(value):
    if value is None:
        return ''
    return str(value).replace('-', MINUS_SIGN)
