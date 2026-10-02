# Simulated payment provider. A real provider would get an API call here;
# the result always arrives later through the webhook
# (simulate it with: python manage.py send_test_webhook <provider_reference> succeeded).


def create_order(provider_reference, amount):
    return provider_reference
