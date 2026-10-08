# -*- coding: utf-8 -*-
"""
Data Factory - synthetic test data generation
Generate test data with Faker
"""
from typing import Dict, Any, List, Optional
from faker import Faker
import random
import string


class DataFactory:
    """Synthetic test data factory"""

    def __init__(self, locale: str = "en_US"):
        """
        Initialize the data factory

        Args:
            locale: Locale; defaults to American English
        """
        self.fake = Faker(locale)
        Faker.seed(None)  # Use fresh randomness each time

        # Predefined data-generator mapping
        self._generators = {
            # Personal information
            "name": self.fake.name,
            "first_name": self.fake.first_name,
            "last_name": self.fake.last_name,
            "phone": self.fake.phone_number,
            "phone_number": self.fake.phone_number,
            "email": self.fake.email,
            "ssn": self.fake.ssn,
            "id_card": self.fake.ssn,

            # Addresses
            "address": self.fake.address,
            "city": self.fake.city,
            "province": getattr(self.fake, "province", None) or self.fake.state,
            "street_address": self.fake.street_address,
            "postcode": self.fake.postcode,

            # Company
            "company": self.fake.company,
            "job": self.fake.job,

            # Network
            "url": self.fake.url,
            "domain": self.fake.domain_name,
            "ip": self.fake.ipv4,
            "user_agent": self.fake.user_agent,

            # Text
            "text": self.fake.text,
            "sentence": self.fake.sentence,
            "paragraph": self.fake.paragraph,
            "word": self.fake.word,

            # Date and time
            "date": lambda: self.fake.date(),
            "datetime": lambda: self.fake.date_time().isoformat(),
            "time": lambda: self.fake.time(),
            "year": lambda: str(self.fake.year()),
            "month": lambda: str(self.fake.month()),

            # Numbers
            "integer": lambda: random.randint(1, 1000),
            "float": lambda: round(random.uniform(0, 1000), 2),
            "price": lambda: round(random.uniform(10, 9999), 2),

            # Other
            "uuid": self.fake.uuid4,
            "password": lambda: self.fake.password(length=12),
            "username": self.fake.user_name,
        }

    def generate(self, template: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate one record from a template

        Args:
            template: Data template mapping field names to data types
                      For example: {"name": "name", "phone": "phone_number"}

        Returns:
            Generated data dictionary
        """
        result = {}
        for field_name, data_type in template.items():
            if isinstance(data_type, str):
                # Look up string data types in the predefined generators
                generator = self._generators.get(data_type)
                if generator:
                    result[field_name] = generator()
                else:
                    # Keep the original value for unknown types
                    result[field_name] = data_type
            elif isinstance(data_type, dict):
                # Nested template
                result[field_name] = self.generate(data_type)
            elif isinstance(data_type, list) and len(data_type) > 0:
                # Choose a random list item
                result[field_name] = random.choice(data_type)
            else:
                # Keep the original value
                result[field_name] = data_type

        return result

    def generate_batch(self, template: Dict[str, Any], count: int = 10) -> List[Dict[str, Any]]:
        """
        Generate a batch of records

        Args:
            template: Data template
            count: Number of records

        Returns:
            List of records
        """
        return [self.generate(template) for _ in range(count)]

    def get_available_types(self) -> List[str]:
        """Get all available data types"""
        return list(self._generators.keys())


# Global singleton
_factory: Optional[DataFactory] = None


def get_data_factory(locale: str = "en_US") -> DataFactory:
    """Get the data-factory singleton"""
    global _factory
    if _factory is None:
        _factory = DataFactory(locale)
    return _factory


# Convenience functions
def generate_test_data(template: Dict[str, Any]) -> Dict[str, Any]:
    """Generate one test record"""
    return get_data_factory().generate(template)


def generate_test_data_batch(template: Dict[str, Any], count: int = 10) -> List[Dict[str, Any]]:
    """Generate a batch of test records"""
    return get_data_factory().generate_batch(template, count)
