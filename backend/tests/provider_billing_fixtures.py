"""Synthetic-only prices and adapter protocol. Not production provider rates."""
from backend.app.provider_billing import ProviderSpendPolicy


def fake_spend_policy(**changes):
    values = dict(policy_id='test-price-v1', adapter_id='synthetic-byte-token-v1',
        model_id='test-model', task_types=('tactical_report', 'report'), currency='USD',
        max_input_bytes=1000000, max_output_tokens=25, input_byte_price='0', output_token_price='0.01')
    return ProviderSpendPolicy(**{**values, **changes})
