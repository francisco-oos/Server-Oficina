# Permisos técnicos del sistema. Los perfiles/roles de negocio NO están
# hardcodeados: un administrador puede crear roles nuevos y seleccionar estos
# permisos desde la UI/API. Los roles de ROLE_MAP son semillas protegidas para
# que una instalación nueva siempre tenga perfiles funcionales de partida.
PERMISSIONS = {
    "dashboard.view": "Ver dashboard de Oficina",
    "person.view": "Consultar personal",
    "person.edit": "Alta/recontratación/cambios autorizados",
    "attendance.import": "Importar asistencia",
    "attendance.manage": "Capturar/corregir asistencia manual",
    "imports.commit": "Confirmar importaciones",
    "epp.view": "Consultar EPP",
    "epp.request": "Solicitar cambio/reposición de EPP",
    "epp.validate_hr": "Validar EPP como RRHH",
    "training.view": "Consultar capacitación",
    "training.schedule_hr": "Programar/lista de espera desde RRHH",
    "training.confirm_hse": "Confirmar curso desde Seguridad/HSE",
    "cases.create": "Crear casos y evidencias",
    "cases.resolve": "Resolver casos como área competente",
    "projects.manage": "Administrar proyectos/grupos",
    "users.manage": "Administrar usuarios",
    "roles.manage": "Crear y editar perfiles/roles y sus permisos",
    "catalogs.manage": "Administrar catálogos operativos configurables",
    "organizations.manage": "Administrar empresas/outsourcing/proveedores",
    "locations.manage": "Administrar campamentos, almacenes y ubicaciones",
    "assets.view": "Consultar activos e inventario",
    "assets.create": "Dar de alta activos y sus identificadores",
    "assets.edit": "Editar metadatos vigentes de activos",
    "assets.move": "Asignar, transferir, entregar y devolver activos",
    "assets.bulk": "Carga masiva de activos",
    "nodes.view": "Consultar tracking de nodos",
    "nodes.operate": "Registrar tendido, rotación, levantado, retorno y excepciones",
    "maintenance.view": "Consultar taller y mantenimiento",
    "maintenance.manage": "Abrir/diagnosticar/cerrar mantenimiento",
    "inventory.manage": "Abrir y capturar inventarios físicos",
    "inventory.closeout": "Cerrar conciliaciones de inventario/proyecto",
    "transport.view": "Consultar unidades, conductores y asignaciones de transporte",
    "transport.manage": "Administrar unidades, conductores, checklist e incidencias de transporte",
    "evidence.view": "Consultar evidencias vinculadas",
    "evidence.manage": "Configurar repositorios y cargar evidencias",
    "audit.view": "Consultar auditoría",
    "dashboard.configure": "Modo DEV: definir qué widgets aparecen en cada vista resumen",
}

ROLE_MAP = {
    "ADMIN": set(PERMISSIONS),
    "OFFICE": {
        "dashboard.view", "person.view", "epp.view", "epp.request",
        "training.view", "cases.create", "assets.view", "evidence.view",
    },
    "HR": {
        "dashboard.view", "person.view", "person.edit", "attendance.import",
        "attendance.manage", "imports.commit", "epp.view", "epp.request",
        "epp.validate_hr", "training.view", "training.schedule_hr",
        "cases.create", "cases.resolve", "projects.manage", "organizations.manage",
        "transport.view",
    },
    "HSE": {
        "dashboard.view", "person.view", "training.view", "training.confirm_hse",
        "cases.create", "evidence.view",
    },
    "SUPERVISOR": {
        "dashboard.view", "person.view", "epp.view", "epp.request",
        "training.view", "cases.create", "assets.view", "assets.move",
        "nodes.view", "nodes.operate", "inventory.manage", "evidence.view",
        "transport.view",
    },
    "MATERIAL": {
        "dashboard.view", "assets.view", "assets.create", "assets.edit",
        "assets.move", "assets.bulk", "inventory.manage", "inventory.closeout",
        "nodes.view", "evidence.view", "transport.view",
    },
    "TALLER": {
        "dashboard.view", "assets.view", "nodes.view", "maintenance.view",
        "maintenance.manage", "evidence.view", "transport.view",
    },
    # Transporte administra su propio dominio y consulta personal/activos para
    # resolver el vínculo persona ↔ unidad ↔ conductor ↔ grupo sin duplicarlo.
    "TRANSPORTE": {
        "dashboard.view", "person.view", "assets.view", "assets.move",
        "transport.view", "transport.manage", "maintenance.view",
        "cases.create", "evidence.view",
    },
}
