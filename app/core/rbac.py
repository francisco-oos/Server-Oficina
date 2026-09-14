PERMISSIONS = {
    "dashboard.view": "Ver dashboard de Oficina",
    "person.view": "Consultar personal",
    "person.edit": "Alta/recontratación/cambios autorizados",
    "attendance.import": "Importar asistencia",
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
    "users.manage": "Administrar usuarios y roles",
    "audit.view": "Consultar auditoría",
}

ROLE_MAP = {
    "ADMIN": set(PERMISSIONS),
    "OFFICE": {"dashboard.view", "person.view", "epp.view", "epp.request", "training.view", "cases.create"},
    "HR": {"dashboard.view", "person.view", "person.edit", "attendance.import", "imports.commit", "epp.view", "epp.request", "epp.validate_hr", "training.view", "training.schedule_hr", "cases.create", "cases.resolve", "projects.manage"},
    "HSE": {"dashboard.view", "person.view", "training.view", "training.confirm_hse", "cases.create"},
    "SUPERVISOR": {"dashboard.view", "person.view", "epp.view", "epp.request", "training.view", "cases.create"},
}
