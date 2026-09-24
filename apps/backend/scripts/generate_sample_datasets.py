"""Generate the onboarding sample datasets (#770).

The files in ``app/sample_datasets/`` are synthetic but plausible. Every row is drawn
from the seeded relationships below, so a model has real signal to learn and the
score the onboarding copy quotes (``expected_accuracy`` in onboarding_service.py)
can be measured instead of assumed. Re-run after changing a relationship, then
re-measure: ``tests/test_services/test_sample_datasets.py`` fails when a stated
score is no longer reached.

    uv run python scripts/generate_sample_datasets.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "app" / "sample_datasets"
SEED = 770


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-x))


def customer_churn(rng: np.random.Generator, n: int = 2000) -> pd.DataFrame:
    contract = rng.choice(["Month-to-month", "One year", "Two year"], n, p=[0.55, 0.21, 0.24])
    tenure = np.where(
        contract == "Month-to-month", rng.integers(1, 40, n), rng.integers(6, 73, n)
    )
    internet = rng.choice(["DSL", "Fiber optic", "No"], n, p=[0.34, 0.44, 0.22])
    has_net = internet != "No"

    def addon(p: float) -> np.ndarray:
        return np.where(has_net, rng.choice(["Yes", "No"], n, p=[p, 1 - p]), "No internet service")

    online_security, online_backup = addon(0.29), addon(0.34)
    device_protection, tech_support = addon(0.34), addon(0.29)
    streaming_tv, streaming_movies = addon(0.38), addon(0.39)
    phone = rng.choice(["Yes", "No"], n, p=[0.9, 0.1])
    multiple_lines = np.where(phone == "Yes", rng.choice(["Yes", "No"], n, p=[0.47, 0.53]), "No phone service")
    payment = rng.choice(
        ["Electronic check", "Mailed check", "Bank transfer", "Credit card"], n, p=[0.34, 0.23, 0.22, 0.21]
    )
    base = np.select([internet == "Fiber optic", internet == "DSL"], [70.0, 45.0], 20.0)
    extras = sum((a == "Yes") * 5.0 for a in (online_security, online_backup, device_protection, tech_support))
    extras = extras + (streaming_tv == "Yes") * 9.0 + (streaming_movies == "Yes") * 9.0 + (multiple_lines == "Yes") * 5.0
    monthly = np.round(base + extras + rng.normal(0, 3, n), 2)
    total = np.round(monthly * tenure * rng.uniform(0.95, 1.05, n), 2)
    senior = (rng.random(n) < 0.16).astype(int)
    partner = rng.choice(["Yes", "No"], n)
    dependents = rng.choice(["Yes", "No"], n, p=[0.3, 0.7])

    logit = (
        -2.2
        + 2.6 * (contract == "Month-to-month")
        - 1.6 * (contract == "Two year")
        - 0.075 * tenure
        + 1.5 * (internet == "Fiber optic")
        + 1.0 * (payment == "Electronic check")
        - 1.0 * (tech_support == "Yes")
        - 0.9 * (online_security == "Yes")
        + 0.6 * senior
        - 0.5 * (dependents == "Yes")
    )
    churn = (rng.random(n) < _sigmoid(logit)).astype(int)
    return pd.DataFrame(
        {
            "tenure": tenure,
            "monthly_charges": monthly,
            "total_charges": total,
            "contract_type": contract,
            "payment_method": payment,
            "internet_service": internet,
            "online_security": online_security,
            "online_backup": online_backup,
            "device_protection": device_protection,
            "tech_support": tech_support,
            "streaming_tv": streaming_tv,
            "streaming_movies": streaming_movies,
            "gender": rng.choice(["Female", "Male"], n),
            "senior_citizen": senior,
            "partner": partner,
            "dependents": dependents,
            "phone_service": phone,
            "multiple_lines": multiple_lines,
            "churn": churn,
        }
    )


def house_prices(rng: np.random.Generator, n: int = 3000) -> pd.DataFrame:
    # Seattle-area zip codes with a location premium and a centroid.
    zips = {
        98103: (1.25, 47.671, -122.342), 98115: (1.30, 47.685, -122.300), 98117: (1.22, 47.689, -122.377),
        98125: (1.05, 47.716, -122.300), 98133: (0.95, 47.740, -122.343), 98144: (1.10, 47.585, -122.293),
        98178: (0.80, 47.499, -122.247), 98118: (0.90, 47.541, -122.271), 98106: (0.85, 47.534, -122.349),
        98199: (1.45, 47.651, -122.397), 98112: (1.80, 47.630, -122.298), 98004: (2.10, 47.616, -122.205),
        98033: (1.60, 47.679, -122.195), 98052: (1.45, 47.679, -122.121), 98059: (1.00, 47.481, -122.132),
        98031: (0.80, 47.410, -122.194), 98042: (0.75, 47.367, -122.114), 98023: (0.72, 47.310, -122.360),
    }
    zip_codes = np.array(list(zips))
    zipcode = rng.choice(zip_codes, n)
    premium = np.array([zips[z][0] for z in zipcode])
    lat = np.round(np.array([zips[z][1] for z in zipcode]) + rng.normal(0, 0.012, n), 4)
    long = np.round(np.array([zips[z][2] for z in zipcode]) + rng.normal(0, 0.012, n), 3)

    sqft = np.clip(rng.lognormal(7.55, 0.38, n), 520, 6500).round(-1).astype(int)
    bedrooms = np.clip(np.round(sqft / 650 + rng.normal(0.8, 0.7, n)), 1, 7).astype(int)
    bathrooms = np.clip(np.round((sqft / 900 + rng.normal(0.3, 0.4, n)) * 4) / 4, 0.75, 5.5)
    floors = rng.choice([1, 1.5, 2, 3], n, p=[0.48, 0.09, 0.39, 0.04])
    waterfront = (rng.random(n) < 0.012).astype(int)
    view = np.where(waterfront == 1, rng.integers(3, 5, n), rng.choice(range(5), n, p=[0.88, 0.03, 0.05, 0.03, 0.01]))
    condition = rng.choice([1, 2, 3, 4, 5], n, p=[0.01, 0.02, 0.62, 0.27, 0.08])
    grade = np.clip(np.round(4.5 + sqft / 700 + rng.normal(0, 0.8, n)), 4, 12).astype(int)
    yr_built = rng.integers(1900, 2016, n)
    renovated = (yr_built < 1980) & (rng.random(n) < 0.12)
    yr_renovated = np.where(renovated, rng.integers(1985, 2016, n), 0)
    sqft_living15 = np.clip(sqft * rng.normal(0.9, 0.18, n), 600, 5500).round(-1).astype(int)
    sqft_lot15 = np.clip(rng.lognormal(8.9, 0.5, n), 1200, 40000).round(-1).astype(int)

    log_price = (
        6.6
        + 0.85 * np.log(sqft)
        + 0.09 * (grade - 7)
        + 0.05 * (condition - 3)
        + 0.06 * view
        + 0.45 * waterfront
        + np.log(premium)
        + 0.06 * renovated
        - 0.0006 * (2015 - yr_built)
        + rng.normal(0, 0.14, n)
    )
    price = (np.exp(log_price) / 1000).round() * 1000
    return pd.DataFrame(
        {
            "sqft": sqft,
            "bedrooms": bedrooms,
            "bathrooms": bathrooms,
            "floors": floors,
            "waterfront": waterfront,
            "view": view,
            "condition": condition,
            "grade": grade,
            "yr_built": yr_built,
            "yr_renovated": yr_renovated,
            "zipcode": zipcode,
            "lat": lat,
            "long": long,
            "sqft_living15": sqft_living15,
            "sqft_lot15": sqft_lot15,
            "price": price.astype(int),
        }
    )


def marketing_response(rng: np.random.Generator, n: int = 2500) -> pd.DataFrame:
    age = np.clip(rng.normal(44, 13, n), 18, 85).astype(int)
    education = rng.choice(["High School", "Graduate", "Master", "PhD"], n, p=[0.3, 0.45, 0.18, 0.07])
    edu_bonus = np.select([education == "PhD", education == "Master", education == "Graduate"], [30000, 18000, 9000], 0)
    income = np.clip(rng.normal(42000 + 450 * age, 16000, n) + edu_bonus, 12000, 220000).round(-2).astype(int)
    marital = rng.choice(["Single", "Married", "Divorced", "Widowed"], n, p=[0.33, 0.5, 0.13, 0.04])
    kids = rng.choice([0, 1, 2, 3], n, p=[0.45, 0.3, 0.2, 0.05])
    channel = rng.choice(["email", "phone", "social", "direct_mail"], n, p=[0.4, 0.2, 0.25, 0.15])
    previous = rng.poisson(np.clip(income / 12000, 1, 15)).astype(int)
    days_since = rng.integers(1, 366, n)
    total_spent = np.round(previous * rng.gamma(4, 45, n), 2)
    segment = np.select([total_spent > 2500, total_spent > 900], ["Premium", "Standard"], "Basic")
    recency = 5 - np.minimum(days_since // 73, 4)
    frequency = np.clip(previous // 3 + 1, 1, 5)
    monetary = np.clip(np.digitize(total_spent, [300, 900, 1800, 3000]) + 1, 1, 5)
    campaign = rng.choice(["C101", "C102", "C103", "C104"], n)
    offer = rng.choice(["discount", "free_shipping", "bundle", "loyalty_points"], n)
    discount = np.where(offer == "discount", rng.choice([10, 15, 20, 25], n), 0)

    logit = (
        -1.6
        + 0.9 * (recency - 3)
        + 0.7 * (frequency - 2)
        + 1.6 * (channel == "email")
        + 1.0 * (channel == "phone") * (age >= 55)
        + 1.0 * (channel == "social") * (age < 35)
        - 1.0 * (channel == "direct_mail")
        + 0.08 * discount
        + 0.8 * (offer == "free_shipping") * (kids > 0)
        - 0.4 * kids
    )
    responded = (rng.random(n) < _sigmoid(logit)).astype(int)
    return pd.DataFrame(
        {
            "age": age,
            "income": income,
            "education": education,
            "marital_status": marital,
            "kids_at_home": kids,
            "campaign_channel": channel,
            "previous_purchases": previous,
            "customer_segment": segment,
            "days_since_last_purchase": days_since,
            "total_spent": total_spent,
            "recency_score": recency,
            "frequency_score": frequency,
            "monetary_score": monetary,
            "campaign_id": campaign,
            "offer_type": offer,
            "discount_percent": discount,
            "responded": responded,
        }
    )


def main() -> None:
    rng = np.random.default_rng(SEED)
    for name, build in (
        ("customer_churn", customer_churn),
        ("house_prices", house_prices),
        ("marketing_response", marketing_response),
    ):
        df = build(rng)
        df.to_csv(OUT / f"{name}.csv", index=False)
        print(f"{name}: {len(df)} rows x {len(df.columns)} columns")


if __name__ == "__main__":
    main()
