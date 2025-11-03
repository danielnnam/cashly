from django import template

register = template.Library()

@register.filter
def initials(value):
    if not value:
        return ""
    words = value.split()
    return "".join([w[0].upper() for w in words])
