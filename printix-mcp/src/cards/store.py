import json
from typing import Any

from db import (
    clone_card_profile,
    create_card_profile,
    delete_card_mapping,
    delete_card_profile,
    get_card_mapping_by_card_id,
    get_card_profile,
    list_card_mappings,
    list_card_profiles,
    upsert_card_mapping,
    update_card_profile,
)
from .profiles import get_builtin_profiles


class CardMappingStore:
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id

    def list_profiles(self) -> list[dict[str, Any]]:
        return get_builtin_profiles() + list_card_profiles(self.tenant_id)

    def get_profile(self, profile_id: str) -> dict[str, Any] | None:
        for p in get_builtin_profiles():
            if p['id'] == profile_id:
                return p
        return get_card_profile(profile_id, tenant_id=self.tenant_id)

    def save_profile(self, *, profile_id: str = '', name: str, vendor: str = '', reader_model: str = '', mode: str = '', description: str = '', rules: dict[str, Any] | None = None, is_active: bool = True) -> dict[str, Any]:
        rules_json = json.dumps(rules or {}, ensure_ascii=False)
        if profile_id:
            return update_card_profile(profile_id, tenant_id=self.tenant_id, name=name, vendor=vendor, reader_model=reader_model, mode=mode, description=description, rules_json=rules_json, is_active=is_active)
        return create_card_profile(tenant_id=self.tenant_id, name=name, vendor=vendor, reader_model=reader_model, mode=mode, description=description, rules_json=rules_json, is_active=is_active)

    def clone_profile(self, profile_id: str, new_name: str = "") -> dict | None:
        return clone_card_profile(profile_id, tenant_id=self.tenant_id, new_name=new_name or None)

    def delete_profile(self, profile_id: str) -> bool:
        return delete_card_profile(profile_id, tenant_id=self.tenant_id)

    def save_mapping(self, mapping: dict[str, Any]) -> dict[str, Any]:
        return upsert_card_mapping(**mapping)

    def get_mapping(self, printix_card_id: str) -> dict[str, Any] | None:
        return get_card_mapping_by_card_id(self.tenant_id, printix_card_id)

    def delete_mapping(self, printix_card_id: str) -> bool:
        return delete_card_mapping(self.tenant_id, printix_card_id)

    def search(self, query: str = '') -> list[dict[str, Any]]:
        return list_card_mappings(self.tenant_id, query=query)
