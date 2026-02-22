from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class CountryProfile:
    code: str
    name: str
    currency: str
    default_tax_rate: float
    unusual_amount_threshold: float
    tax_deadline_day: int
    expense_keywords: dict[str, str] = field(default_factory=dict)
    income_keywords: dict[str, str] = field(default_factory=dict)


_PROFILES: dict[str, CountryProfile] = {
    "AU": CountryProfile(
        code="AU",
        name="Australia",
        currency="AUD",
        default_tax_rate=0.10,
        unusual_amount_threshold=12000.0,
        tax_deadline_day=21,
        expense_keywords={
            "adwords": "Marketing",
            "officeworks": "Office Supplies",
            "xero": "Software",
            "fuel": "Transport",
            "superannuation": "Payroll",
        },
        income_keywords={
            "invoice": "Consulting Income",
            "retainer": "Retainer Income",
        },
    ),
    "US": CountryProfile(
        code="US",
        name="United States",
        currency="USD",
        default_tax_rate=0.0,
        unusual_amount_threshold=10000.0,
        tax_deadline_day=15,
        expense_keywords={
            "quickbooks": "Software",
            "stripe fee": "Bank Fees",
            "google ads": "Marketing",
            "payroll": "Payroll",
            "uber": "Transport",
        },
        income_keywords={
            "consulting": "Consulting Income",
            "subscription": "Subscription Income",
        },
    ),
    "UK": CountryProfile(
        code="UK",
        name="United Kingdom",
        currency="GBP",
        default_tax_rate=0.20,
        unusual_amount_threshold=9000.0,
        tax_deadline_day=7,
        expense_keywords={
            "hmrc": "Tax",
            "trainline": "Transport",
            "mailchimp": "Marketing",
            "sage": "Software",
        },
        income_keywords={
            "project": "Project Income",
            "freelance": "Freelance Income",
        },
    ),
    "IN": CountryProfile(
        code="IN",
        name="India",
        currency="INR",
        default_tax_rate=0.18,
        unusual_amount_threshold=300000.0,
        tax_deadline_day=20,
        expense_keywords={
            "gst": "Tax",
            "zoho": "Software",
            "petrol": "Transport",
            "internet": "Utilities",
        },
        income_keywords={
            "service": "Service Income",
            "advance": "Advance Income",
        },
    ),
    "FR": CountryProfile(
        code="FR",
        name="France",
        currency="EUR",
        default_tax_rate=0.20,
        unusual_amount_threshold=9500.0,
        tax_deadline_day=15,
        expense_keywords={
            "urssaf": "Charges Sociales",
            "sncf": "Transport",
            "publicite": "Marketing",
            "logiciel": "Software",
        },
        income_keywords={
            "mission": "Mission Income",
            "acompte": "Advance Income",
        },
    ),
    "CUSTOM": CountryProfile(
        code="CUSTOM",
        name="Custom",
        currency="USD",
        default_tax_rate=0.0,
        unusual_amount_threshold=10000.0,
        tax_deadline_day=15,
        expense_keywords={},
        income_keywords={},
    ),
}


def list_supported_countries() -> list[str]:
    return sorted(_PROFILES.keys())


def get_country_profile(country: str, *, currency_override: str | None = None) -> CountryProfile:
    profile = _PROFILES.get(country.upper(), _PROFILES["CUSTOM"])
    if currency_override:
        return CountryProfile(
            code=profile.code,
            name=profile.name,
            currency=currency_override,
            default_tax_rate=profile.default_tax_rate,
            unusual_amount_threshold=profile.unusual_amount_threshold,
            tax_deadline_day=profile.tax_deadline_day,
            expense_keywords=profile.expense_keywords.copy(),
            income_keywords=profile.income_keywords.copy(),
        )
    return profile

