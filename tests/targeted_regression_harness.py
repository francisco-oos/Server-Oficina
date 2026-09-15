from dataclasses import dataclass


@dataclass
class AssetType:
    capabilities: list[str]


@dataclass
class Asset:
    asset_type: AssetType


def has_capability(asset: Asset, capability: str) -> bool:
    return capability in (asset.asset_type.capabilities or [])


def is_driver(person_id: str, driver_person_id: str | None) -> bool:
    return bool(driver_person_id and driver_person_id == person_id)


assert has_capability(Asset(AssetType(["node_field"])), "radio") is False
assert has_capability(Asset(AssetType(["radio"])), "radio") is True
assert has_capability(Asset(AssetType(["phone"])), "phone") is True
assert is_driver("A", "B") is False
assert is_driver("A", "A") is True

print("TARGETED_REGRESSION_RULES_OK")
