from __future__ import annotations

import random
import re
from typing import Dict


def generate_safe_name_part(generator):
    while True:
        name = re.sub(r"\s+", " ", generator()).strip()
        if re.fullmatch(r"[A-Za-z]+(?: [A-Za-z]+)*", name):
            return name


def to_email_part(name: str) -> str:
    return re.sub(r"\s+", "", re.sub(r"[^A-Za-z\s]", " ", name)).lower()


def create_account_generator(config):
    firsts = ["Alice", "Bob", "Carol", "David", "Emma", "Frank", "Grace", "Henry", "Ivy", "Jack"]
    lasts = ["Smith", "Johnson", "Brown", "Taylor", "Anderson", "Thomas", "Moore", "Martin", "Lee", "Clark"]
    domains = config.get("domains") or ["mail.com"]

    def generate_account():
        domain = random.choice(domains)
        first_name = generate_safe_name_part(lambda: random.choice(firsts))
        last_name = generate_safe_name_part(lambda: random.choice(lasts))
        full_name = f"{first_name} {last_name}"
        email = f"{to_email_part(first_name)}{to_email_part(last_name)}@{domain}"
        return {
            "email": email,
            "firstName": first_name,
            "lastName": last_name,
            "fullName": full_name,
        }

    return generate_account
