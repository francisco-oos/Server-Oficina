from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.rbac import PERMISSIONS, ROLE_MAP
from app.db.models import AssetTechnology, AssetType, CatalogItem, Permission, Role


# Catálogos iniciales. Se usan como semillas editables; el motor consulta los
# metadatos en base de datos y admite nuevos códigos sin cambios de código.
CATALOG_SEEDS = {
    "ASSET_STATUS": [
        ("AVAILABLE", "Disponible", {"critical": False, "transferable": True}),
        ("ASSIGNED", "Asignado", {"critical": False, "transferable": True}),
        ("DEPLOYED", "Tendido / en campo", {"critical": False, "transferable": False}),
        ("RETURNED", "Retornado", {"critical": False, "transferable": True}),
        ("MAINTENANCE", "En mantenimiento", {"critical": False, "transferable": False}),
        ("DAMAGED", "Dañado", {"critical": True, "transferable": False}),
        ("BURNED", "Quemado", {"critical": True, "transferable": False}),
        ("MISSING", "No encontrado", {"critical": True, "transferable": False}),
        ("LOST", "Extraviado", {"critical": True, "transferable": False}),
        ("STOLEN", "Robado", {"critical": True, "transferable": False}),
        ("SEIZED", "Incautado", {"critical": True, "transferable": False}),
        ("HIBERNATED", "Hibernado", {"critical": False, "transferable": True}),
        ("NO_INFO", "Retorno sin información", {"critical": True, "transferable": False}),
        ("RETIRED", "Baja", {"critical": False, "transferable": False}),
    ],
    "ASSET_MOVEMENT": [
        ("REGISTER", "Alta", {"status_after": "AVAILABLE"}),
        ("ASSIGN", "Asignación / entrega", {"status_after": "ASSIGNED", "opens_custody": True}),
        ("RETURN", "Devolución", {"status_after": "AVAILABLE", "closes_custody": True}),
        ("TRANSFER", "Transferencia", {}),
        ("TENDIDO", "Tendido", {"status_after": "DEPLOYED", "requires_capability": "node_field"}),
        ("ROTACION", "Rotación", {"status_after": "DEPLOYED", "requires_capability": "node_field"}),
        ("LEVANTADO", "Levantado", {"status_after": "RETURNED", "requires_capability": "node_field"}),
        ("RETORNO", "Retorno", {"status_after": "RETURNED", "requires_capability": "node_field"}),
        ("DAMAGE", "Dañado", {"status_after": "DAMAGED"}),
        ("BURNED", "Quemado", {"status_after": "BURNED"}),
        ("MISSING", "No encontrado", {"status_after": "MISSING"}),
        ("LOST", "Extraviado", {"status_after": "LOST"}),
        ("STOLEN", "Robado", {"status_after": "STOLEN"}),
        ("SEIZED", "Incautado", {"status_after": "SEIZED"}),
        ("MAINTENANCE_IN", "Entrada a mantenimiento", {"status_after": "MAINTENANCE"}),
        ("MAINTENANCE_OUT", "Salida de mantenimiento", {"status_after": "AVAILABLE"}),
        ("HIBERNATE", "Hibernar", {"status_after": "HIBERNATED"}),
        ("WAKE", "Deshibernar", {"status_after": "AVAILABLE"}),
        ("RECOVER", "Recuperado", {"status_after": "AVAILABLE"}),
        ("NO_INFO", "Retorno sin información", {"status_after": "NO_INFO"}),
        ("RETIRE", "Baja de activo", {"status_after": "RETIRED"}),
    ],
    "NODE_OPERATION": [
        ("TENDIDO", "Tendido", {"movement_type": "TENDIDO"}),
        ("ROTACION", "Rotación", {"movement_type": "ROTACION"}),
        ("LEVANTADO", "Levantado", {"movement_type": "LEVANTADO"}),
        ("RETORNO", "Retorno", {"movement_type": "RETORNO"}),
        ("INCIDENT", "Incidencia / excepción", {"movement_type": None}),
    ],
    "NODE_RESULT": [
        ("OK", "Sano / OK", {}),
        # NODE_RESULT desacopla el resultado de campo del nombre técnico del movimiento.
        # Esto evita hardcodear equivalencias como DAMAGED->DAMAGE en el endpoint.
        ("DAMAGED", "Dañado", {"status_after": "DAMAGED", "movement_type": "DAMAGE"}),
        ("BURNED", "Quemado", {"status_after": "BURNED", "movement_type": "BURNED"}),
        ("MISSING", "No encontrado", {"status_after": "MISSING", "movement_type": "MISSING"}),
        ("LOST", "Extraviado", {"status_after": "LOST", "movement_type": "LOST"}),
        ("STOLEN", "Robado", {"status_after": "STOLEN", "movement_type": "STOLEN"}),
        ("SEIZED", "Incautado", {"status_after": "SEIZED", "movement_type": "SEIZED"}),
        ("MAINTENANCE", "Enviar a mantenimiento", {"status_after": "MAINTENANCE", "movement_type": "MAINTENANCE_IN"}),
        ("HIBERNATED", "Hibernado", {"status_after": "HIBERNATED", "movement_type": "HIBERNATE"}),
        ("NO_INFO", "Sin información", {"status_after": "NO_INFO", "movement_type": "NO_INFO"}),
    ],
    "ATTENDANCE_STATUS": [
        ("PRESENT", "Presente", {}), ("ABSENT", "Ausente", {}),
        ("REST", "Descanso", {}), ("LEAVE", "Permiso", {}),
        ("MEDICAL", "Incapacidad médica", {}), ("VACATION", "Vacaciones", {}),
    ],
    "EMPLOYMENT_EVENT": [
        ("RESIGNATION", "Renuncia", {"closes_engagement": True, "final_status": "ENDED"}),
        ("DISMISSAL", "Despido", {"closes_engagement": True, "final_status": "ENDED"}),
        ("CONTRACT_END", "Fin de contrato", {"closes_engagement": True, "final_status": "ENDED"}),
        ("TRANSFER", "Cambio / transferencia", {"closes_engagement": False}),
        ("LICENSE_UPDATE", "Actualización de licencia", {"closes_engagement": False}),
    ],
    "LOCATION_TYPE": [
        ("CAMP", "Campamento", {}), ("OFFICE", "Oficina", {}),
        ("WAREHOUSE", "Almacén", {}), ("FIELD", "Campo", {}),
        ("WORKSHOP", "Taller", {}), ("LINE", "Línea / frente", {}),
        ("OTHER", "Otra", {}),
    ],
    "MAINTENANCE_STATUS": [
        ("OPEN", "Abierta", {}), ("DIAGNOSIS", "Diagnóstico", {}),
        ("WAITING_PART", "Espera de pieza", {}), ("REPAIRED", "Reparado", {}),
        ("TESTING", "En prueba", {}), ("CLOSED", "Cerrada", {}),
        ("NOT_REPAIRABLE", "No reparable", {}),
    ],
    "ORGANIZATION_TYPE": [
        ("COMPANY", "Empresa", {}), ("OUTSOURCING", "Outsourcing", {}),
        ("CONTRACTOR", "Contratista", {}), ("CLIENT", "Cliente", {}),
        ("OTHER", "Otra", {}),
    ],
}

ASSET_TYPE_SEEDS = [
    ("NODE", "Nodo sísmico", ["node_field", "custody", "maintenance", "health"]),
    ("RADIO", "Radio", ["custody", "maintenance"]),
    ("ANTENNA", "Antena", ["custody", "maintenance"]),
    ("PHONE", "Teléfono", ["custody", "maintenance", "imei"]),
    ("COMPUTER", "Computadora", ["custody", "maintenance"]),
    ("DRONE", "Drone", ["custody", "maintenance", "health"]),
    ("VEHICLE", "Vehículo / unidad", ["transport", "custody", "maintenance", "health"]),
    ("SERVER", "Servidor", ["maintenance", "health"]),
    ("NAS", "NAS", ["maintenance", "health"]),
]

TECHNOLOGY_SEEDS = [
    ("SERCEL", "Sercel", "Sercel"),
    ("INOVA", "INOVA", "INOVA"),
    ("DJI", "DJI", "DJI"),
    ("GENERIC", "Genérica", None),
]


def ensure_rbac(db: Session) -> None:
    existing = {p.code: p for p in db.scalars(select(Permission)).all()}
    for code, desc in PERMISSIONS.items():
        if code not in existing:
            p = Permission(code=code, description=desc)
            db.add(p)
            existing[code] = p
    db.flush()
    roles = {r.name: r for r in db.scalars(select(Role)).all()}
    for name, codes in ROLE_MAP.items():
        role = roles.get(name)
        if not role:
            role = Role(name=name, description=f"Rol base protegido {name}")
            db.add(role)
            db.flush()
        # Sólo los roles base se resincronizan; los roles personalizados nunca
        # se alteran durante el arranque.
        role.permissions = [existing[c] for c in sorted(codes)]
    db.commit()


def ensure_operational_catalogs(db: Session) -> None:
    for catalog, rows in CATALOG_SEEDS.items():
        existing = {x.code for x in db.scalars(select(CatalogItem).where(CatalogItem.catalog == catalog)).all()}
        for order, (code, name, metadata) in enumerate(rows, start=10):
            if code not in existing:
                db.add(CatalogItem(catalog=catalog, code=code, name=name, sort_order=order, metadata_json=metadata))
    existing_types = {x.code for x in db.scalars(select(AssetType)).all()}
    for code, name, capabilities in ASSET_TYPE_SEEDS:
        if code not in existing_types:
            db.add(AssetType(code=code, name=name, capabilities=capabilities))
    existing_tech = {x.code for x in db.scalars(select(AssetTechnology)).all()}
    for code, name, vendor in TECHNOLOGY_SEEDS:
        if code not in existing_tech:
            db.add(AssetTechnology(code=code, name=name, vendor=vendor))
    db.commit()
