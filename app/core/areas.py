"""Áreas departamentales y autoridad sobre el dato.

Por qué existe este módulo
--------------------------
Server Oficina es un servidor **compartido**: RRHH, Seguridad/HSE, Transporte,
Control de Material, Operación (Tracking Nodes) y Taller/TX trabajan sobre el
mismo Tracking Core. Compartir el núcleo no significa que cualquiera pueda
alterar cualquier dato: cada dominio de información tiene un área que responde
por él.

El RBAC por permisos (``app/core/rbac.py``) responde a *qué operación técnica*
puede ejecutar un usuario. Este módulo responde a una pregunta distinta y
complementaria, que el encargo plantea explícitamente:

======================  ==========================================
QUIÉN ES AUTORIDAD      el área que responde por la veracidad del dato
QUIÉN LO PUEDE CONSULTAR  áreas que lo leen para trabajar
QUIÉN PUEDE PROPONER    áreas que pueden pedir un cambio
QUIÉN PUEDE CONFIRMARLO áreas que lo vuelven oficial
======================  ==========================================

Distinción deliberada: *proponer* ≠ *confirmar*. Operación puede reportar que
un nodo apareció dañado (propuesta, un hecho observado), pero la baja definitiva
del activo la confirma Control de Material. Igual que ``evidencia ≠ sanción``,
aquí ``reporte ≠ resolución``.

Este módulo es **declarativo y sin efectos secundarios**: describe el gobierno
del dato para que la API y la interfaz lo comuniquen de forma coherente. No
sustituye la verificación de permisos, que sigue siendo la que autoriza o niega
cada petición.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: Código del área usada cuando un rol no declara ninguna (administración
#: transversal). Nunca se niega acceso por no tener área: el área matiza y
#: explica, el permiso es lo que autoriza.
AREA_GENERAL = "GENERAL"


@dataclass(frozen=True)
class Area:
    """Un área departamental que opera sobre el Tracking Core."""

    code: str
    name: str
    description: str
    #: Orden sugerido en la navegación lateral de la interfaz.
    sort_order: int = 100


AREAS: dict[str, Area] = {
    "RRHH": Area("RRHH", "Recursos Humanos", "Identidad laboral, contrataciones, asignaciones, asistencia y EPP.", 10),
    "HSE": Area("HSE", "Seguridad / HSE", "Cursos de seguridad, cumplimiento, incidencias HSE y sus evidencias.", 20),
    "TRANSPORTE": Area("TRANSPORTE", "Transporte", "Unidades, conductores, asignaciones, checklist e incidencias de transporte.", 30),
    "MATERIAL": Area("MATERIAL", "Control de Material", "Inventario, custodia, entregas, devoluciones, transferencias y existencia física.", 40),
    "OPERACION": Area("OPERACION", "Operación / Tracking Nodes", "Historia operacional específica de los nodos sísmicos en campo.", 50),
    "TALLER": Area("TALLER", "Taller / TX", "Recepción, diagnóstico, pruebas, reparación y resultados técnicos.", 60),
    "GENERAL": Area(AREA_GENERAL, "Transversal", "Consulta transversal y administración del sistema.", 90),
}


@dataclass(frozen=True)
class DataDomain:
    """Gobierno de un conjunto de datos concreto.

    ``authority`` es el área responsable: quien responde por el dato y quien lo
    vuelve oficial. ``confirm`` existe aparte porque hay datos donde la
    confirmación es compartida (por ejemplo un curso de seguridad que RRHH
    programa y HSE acredita).
    """

    code: str
    name: str
    authority: str
    consult: tuple[str, ...] = ()
    propose: tuple[str, ...] = ()
    confirm: tuple[str, ...] = ()
    #: Nota de negocio: por qué el gobierno es éste y no otro.
    note: str = ""
    #: Permisos técnicos que materializan la autoridad sobre este dominio.
    permissions: tuple[str, ...] = field(default_factory=tuple)


#: Matriz de autoridad. Es la base conceptual del apartado 7 del encargo.
#: Cambiarla es una decisión de gobierno, no un ajuste de interfaz.
DATA_DOMAINS: dict[str, DataDomain] = {
    "PERSON_IDENTITY": DataDomain(
        "PERSON_IDENTITY", "Identidad laboral de la persona", authority="RRHH",
        consult=("HSE", "TRANSPORTE", "MATERIAL", "OPERACION", "TALLER"),
        propose=("HSE", "TRANSPORTE", "OPERACION"), confirm=("RRHH",),
        note="La identidad (person_id) sobrevive a altas, bajas y recontrataciones; sólo RRHH la declara.",
        permissions=("person.edit",),
    ),
    "EMPLOYMENT": DataDomain(
        "EMPLOYMENT", "Contrataciones, altas, bajas y recontrataciones", authority="RRHH",
        consult=("HSE", "TRANSPORTE", "MATERIAL", "OPERACION", "TALLER"),
        propose=(), confirm=("RRHH",),
        note="Persona ≠ contratación: una baja cierra la relación laboral, no la identidad.",
        permissions=("person.edit",),
    ),
    "ASSIGNMENT": DataDomain(
        "ASSIGNMENT", "Grupos, cuadrillas, supervisor y ubicación de la persona", authority="RRHH",
        consult=("HSE", "TRANSPORTE", "MATERIAL", "OPERACION", "TALLER"),
        propose=("TRANSPORTE", "OPERACION"), confirm=("RRHH",),
        note="Operación y Transporte conocen el movimiento real en campo y pueden proponerlo; RRHH lo oficializa.",
        permissions=("person.edit",),
    ),
    "ATTENDANCE": DataDomain(
        "ATTENDANCE", "Asistencia y rotación trabajo/descanso", authority="RRHH",
        consult=("HSE", "TRANSPORTE", "OPERACION"), propose=("OPERACION",), confirm=("RRHH",),
        permissions=("attendance.manage", "attendance.import"),
    ),
    "EPP": DataDomain(
        "EPP", "Solicitudes y entregas de EPP", authority="RRHH",
        consult=("HSE", "MATERIAL", "OPERACION"), propose=("HSE", "OPERACION", "MATERIAL"), confirm=("RRHH",),
        note="Cualquier área solicita; RRHH resuelve. La solicitud no es la entrega.",
        permissions=("epp.validate_hr",),
    ),
    "TRAINING": DataDomain(
        "TRAINING", "Cursos de seguridad y vigencias", authority="HSE",
        consult=("RRHH", "TRANSPORTE", "OPERACION"), propose=("RRHH",), confirm=("HSE",),
        note="RRHH programa y lista de espera; la acreditación del curso la confirma Seguridad/HSE.",
        permissions=("training.confirm_hse",),
    ),
    "HSE_INCIDENT": DataDomain(
        "HSE_INCIDENT", "Incidencias HSE, casos y sus evidencias", authority="HSE",
        consult=("RRHH", "TRANSPORTE", "MATERIAL", "OPERACION"),
        propose=("RRHH", "TRANSPORTE", "MATERIAL", "OPERACION", "TALLER"), confirm=("HSE", "RRHH"),
        note="Evidencia ≠ sanción: el sistema conserva hechos y fuentes; el área competente resuelve.",
        permissions=("cases.resolve",),
    ),
    "TRANSPORT_UNIT": DataDomain(
        "TRANSPORT_UNIT", "Unidades, conductores y asignaciones de transporte", authority="TRANSPORTE",
        consult=("RRHH", "HSE", "MATERIAL", "OPERACION"), propose=("RRHH", "OPERACION"), confirm=("TRANSPORTE",),
        note="El vínculo persona ↔ unidad ↔ conductor ↔ grupo se declara una vez aquí y se consulta desde otras áreas.",
        permissions=("transport.manage",),
    ),
    "TRANSPORT_CHECKLIST": DataDomain(
        "TRANSPORT_CHECKLIST", "Checklist e incidencias de unidades", authority="TRANSPORTE",
        consult=("HSE", "MATERIAL", "TALLER"), propose=("OPERACION", "HSE"), confirm=("TRANSPORTE",),
        permissions=("transport.manage",),
    ),
    "ASSET_INVENTORY": DataDomain(
        "ASSET_INVENTORY", "Existencia física, custodia, entregas y devoluciones", authority="MATERIAL",
        consult=("RRHH", "HSE", "TRANSPORTE", "OPERACION", "TALLER"),
        propose=("OPERACION", "TALLER", "TRANSPORTE"), confirm=("MATERIAL",),
        note="Un faltante de inventario es una observación, no una pérdida definitiva: sólo Material la declara.",
        permissions=("assets.move", "inventory.manage", "inventory.closeout"),
    ),
    "ASSET_IDENTITY": DataDomain(
        "ASSET_IDENTITY", "Identidad del activo: serie, IMEI, QR, número económico", authority="MATERIAL",
        consult=("RRHH", "TRANSPORTE", "OPERACION", "TALLER"), propose=("TALLER", "OPERACION"), confirm=("MATERIAL",),
        note="Activo ≠ proyecto: la identidad sobrevive a transferencias entre proyectos.",
        permissions=("assets.create", "assets.edit"),
    ),
    "NODE_OPERATION": DataDomain(
        "NODE_OPERATION", "Historia operacional de nodos: tendido, rotación, levantado y excepciones", authority="OPERACION",
        consult=("MATERIAL", "TALLER", "HSE"), propose=("MATERIAL", "TALLER"), confirm=("OPERACION",),
        note="Operación registra lo ocurrido en campo; el estado actual del activo se deriva de ese historial.",
        permissions=("nodes.operate",),
    ),
    "MAINTENANCE": DataDomain(
        "MAINTENANCE", "Diagnóstico, pruebas, reparación y resultado técnico", authority="TALLER",
        consult=("MATERIAL", "OPERACION", "TRANSPORTE"), propose=("MATERIAL", "OPERACION", "TRANSPORTE"), confirm=("TALLER",),
        note="Un evento de taller no es un movimiento de custodia: describe la intervención técnica sobre el activo.",
        permissions=("maintenance.manage",),
    ),
    "ASSET_HEALTH": DataDomain(
        "ASSET_HEALTH", "Observaciones de salud, SOH y RUL", authority="TALLER",
        consult=("MATERIAL", "OPERACION"), propose=("MATERIAL", "OPERACION"), confirm=("TALLER",),
        note="Predicción ≠ hecho: una observación SOH/RUL nunca da de baja un activo automáticamente.",
        permissions=("maintenance.manage",),
    ),
    "EVIDENCE": DataDomain(
        "EVIDENCE", "Repositorios y registro de evidencias", authority="GENERAL",
        consult=("RRHH", "HSE", "TRANSPORTE", "MATERIAL", "OPERACION", "TALLER"),
        propose=("RRHH", "HSE", "TRANSPORTE", "MATERIAL", "OPERACION", "TALLER"), confirm=("GENERAL",),
        note="La evidencia es compartida por diseño; el área competente decide qué significa.",
        permissions=("evidence.manage",),
    ),
}


#: Área por defecto de cada rol semilla. Los perfiles personalizados declaran la
#: suya en la tabla ``role_areas`` (ver ``app/db/models.py``), de modo que crear
#: un perfil nuevo no exige tocar código.
DEFAULT_ROLE_AREAS: dict[str, str] = {
    "ADMIN": AREA_GENERAL,
    "OFFICE": AREA_GENERAL,
    "HR": "RRHH",
    "HSE": "HSE",
    "SUPERVISOR": "OPERACION",
    "MATERIAL": "MATERIAL",
    "TALLER": "TALLER",
    "TRANSPORTE": "TRANSPORTE",
}


def domains_for_area(area_code: str) -> dict[str, list[str]]:
    """Agrupa los dominios según el papel que juega ``area_code`` en cada uno.

    Devuelve las cuatro listas del encargo (``authority``/``consult``/
    ``propose``/``confirm``) para que la interfaz pueda explicarle a un usuario
    qué controla su área y qué sólo consulta.
    """
    result: dict[str, list[str]] = {"authority": [], "consult": [], "propose": [], "confirm": []}
    for domain in DATA_DOMAINS.values():
        if domain.authority == area_code:
            result["authority"].append(domain.code)
        if area_code in domain.consult:
            result["consult"].append(domain.code)
        if area_code in domain.propose:
            result["propose"].append(domain.code)
        if area_code in domain.confirm or domain.authority == area_code:
            result["confirm"].append(domain.code)
    return result


def authority_matrix() -> list[dict]:
    """Serializa la matriz completa para API, interfaz y documentación.

    Se expone tal cual para que la matriz publicada en `docs/` y la que muestra
    la interfaz no puedan divergir: ambas leen de aquí.
    """
    return [
        {
            "code": d.code,
            "name": d.name,
            "authority": d.authority,
            "authority_name": AREAS[d.authority].name,
            "consult": list(d.consult),
            "propose": list(d.propose),
            "confirm": list(d.confirm) or [d.authority],
            "permissions": list(d.permissions),
            "note": d.note,
        }
        for d in DATA_DOMAINS.values()
    ]
